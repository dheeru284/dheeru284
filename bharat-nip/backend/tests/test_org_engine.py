"""Agent organization: definitions, workflows, bounds, escalation, approval and logging.
All data is fictional; LLM agents are scripted with MockLLMProvider."""

import uuid

import pytest
from sqlalchemy import func, select

from app.domain.enums import (
    ExecutionKind,
    OrgTaskStatus,
    StepStatus,
    UserRole,
    WorkflowType,
)
from app.models import AuditEvent, Claim, OrgExecution, OrgTaskStep
from app.org import engine, policy
from app.org.agents import AGENTS, CHIEF, AgentDefinition, chain_of_command, direct_reports
from app.org.handlers import HANDLERS
from app.org.policy import Permission, PermissionDenied
from app.org.queries import agent_states, org_chart, task_detail
from app.org.schemas import StrategyOutput
from app.org.tools import TOOLS, ToolContext
from app.org.workflows import WORKFLOWS
from app.services.errors import Conflict, Forbidden
from app.services.storage import save_upload
from app.services.submissions import SubmissionInput, create_submission
from tests import org_scenario as osc
from tests import scenario as sc
from tests.factories import make_user
from tests.helpers import PNG_1X1

REQUIRED_AGENTS = {
    "chief_intelligence_agent",
    "research_agent",
    "claim_extraction_agent",
    "source_verification_agent",
    "fact_check_agent",
    "context_agent",
    "media_forensics_agent",
    "narrative_intelligence_agent",
    "response_strategist",
    "content_agent",
    "localization_agent",
    "critic_agent",
    "compliance_agent",
    "analytics_agent",
}


@pytest.fixture
def org(db_session, settings, world):
    ctx = sc.make_context(db_session, settings, world)
    return world, ctx


def kinds(db, task_id):
    return [
        e.kind.value
        for e in db.scalars(
            select(OrgExecution).where(OrgExecution.task_id == task_id).order_by(OrgExecution.seq)
        )
    ]


# --- definitions -------------------------------------------------------------------------


def test_fourteen_agents_with_complete_definitions():
    assert set(AGENTS) == REQUIRED_AGENTS
    for a in AGENTS.values():
        assert a.role and a.responsibilities and a.input_schema and a.output_schema
        assert a.max_iterations >= 1
        assert a.escalation_rules
        if a.model.value != "rules":
            assert a.max_input_tokens > 0 and a.max_output_tokens > 0
        for t in a.tools:  # every tool's permission is held by the agents that list it
            assert TOOLS[t][0] in a.permissions, (a.key, t)
        # The Chief's delegation and approval are implemented by the engine itself.
        assert a.key in HANDLERS or a.key == CHIEF


def test_hierarchy_is_a_tree_under_the_chief():
    roots = [a.key for a in AGENTS.values() if a.manager is None]
    assert roots == [CHIEF]
    for a in AGENTS.values():
        assert a.manager is None or a.manager in AGENTS
        assert len(chain_of_command(a.key)) < len(AGENTS)  # no cycles
    assert set(direct_reports("research_agent")) == {
        "claim_extraction_agent",
        "source_verification_agent",
        "media_forensics_agent",
    }
    assert AGENTS["critic_agent"].manager == CHIEF and AGENTS["critic_agent"].independent
    assert AGENTS["compliance_agent"].manager == CHIEF and AGENTS["compliance_agent"].independent


def test_no_agent_can_publish_send_or_contact_anyone():
    words = ("publish", "post", "send", "schedule", "contact", "message", "email", "tweet")
    for name in [*TOOLS, *[p.value for p in Permission]]:
        assert not any(w in name.lower() for w in words), name


def test_no_step_is_ever_reviewed_by_its_own_agent():
    for wf in WORKFLOWS.values():
        for step in wf.steps:
            agent = AGENTS[step.agent]
            if step.reviewer.value == "MANAGER":
                assert (agent.manager or CHIEF) != agent.key
            if step.reviewer.value == "CRITIC":
                assert step.agent != "critic_agent"
            assert step.agent != CHIEF  # the Chief delegates and approves, never executes
    assert WORKFLOWS[WorkflowType.NARRATIVE_RESPONSE].approval.value == "HUMAN"


# --- workflows ---------------------------------------------------------------------------


def test_media_check_reports_reuse_and_limitations(db_session, settings, org):
    world, ctx = org
    subs = []
    for _ in range(2):
        f = save_upload(db_session, settings, world.submitter, "poster.png", PNG_1X1)
        s, _ = create_submission(
            db_session, world.submitter, SubmissionInput(submission_type="IMAGE"), stored_file=f
        )
        subs.append(s)
    task = engine.create_task(
        db_session, world.submitter, WorkflowType.MEDIA_CHECK, {"submission_id": str(subs[1].id)}
    )
    engine.run_task(ctx, task.id)
    assert task.status == OrgTaskStatus.COMPLETED
    out = task.output["result"]["media"]
    assert out["file"]["width"] == 1 and out["file"]["content_type"] == "image/png"
    assert len(out["reuse"]) == 1
    assert any("deepfake" in lim for lim in out["limitations"])
    assert kinds(db_session, task.id) == [
        "DELEGATION",
        "EXECUTION",
        "REVIEW",
        "APPROVAL",
        "COMPLETION",
    ]
    review = db_session.scalar(
        select(OrgExecution).where(
            OrgExecution.task_id == task.id, OrgExecution.kind == ExecutionKind.REVIEW
        )
    )
    assert review.agent_key == "research_agent"  # the manager reviews, not the executor
    actions = set(
        db_session.scalars(select(AuditEvent.action).where(AuditEvent.entity_id == str(task.id)))
    )
    assert {
        "org.task_created",
        "org.delegation",
        "org.execution",
        "org.review",
        "org.approval",
        "org.completion",
    } <= actions


def test_submission_fact_check_runs_phase1_pipeline_but_leaves_verdicts_to_humans(db_session, org):
    world, ctx = org
    osc.script_pipeline(world)
    sub = osc.submit(db_session, world)
    task = engine.create_task(
        db_session,
        world.submitter,
        WorkflowType.SUBMISSION_FACT_CHECK,
        {"submission_id": str(sub.id)},
    )
    engine.run_task(ctx, task.id)
    assert task.status == OrgTaskStatus.COMPLETED, task.escalation_reason
    claims = db_session.scalars(select(Claim).where(Claim.submission_id == sub.id)).all()
    assert claims and all(c.status.value == "PENDING_REVIEW" for c in claims)
    fc = task.output["result"]["fact_check"]
    assert fc["pending_human_review"] == len(claims)
    assert all(c["approved_classification"] is None for c in fc["claims"])
    step_tools = [
        c["tool"]
        for e in db_session.scalars(select(OrgExecution).where(OrgExecution.task_id == task.id))
        for c in e.tool_calls
    ]
    assert {"extract_submission", "run_claim_pipeline", "read_fact_check"} <= set(step_tools)


def _investigation(db_session, world, ctx):
    osc.script_pipeline(world)
    from app.pipeline import orchestrator

    [cid] = orchestrator.process_submission(ctx, osc.submit(db_session, world).id)
    return engine.create_task(
        db_session, world.submitter, WorkflowType.CLAIM_INVESTIGATION, {"claim_id": str(cid)}
    )


def test_claim_investigation_with_one_revision(db_session, org):
    world, ctx = org
    task = _investigation(db_session, world, ctx)
    world.llm.script("context_agent", osc.context_output())
    world.llm.script("org_critic", osc.critique("REVISE", ["Name the source in the point."]))
    world.llm.script("context_agent", osc.context_output())
    world.llm.script("org_critic", osc.critique("PASS"))
    engine.run_task(ctx, task.id)
    assert task.status == OrgTaskStatus.COMPLETED
    k = kinds(db_session, task.id)
    assert k.count("REVISION") == 1 and k[-2:] == ["APPROVAL", "COMPLETION"]
    revision_prompt = world.llm.calls_for("context_agent")[1].messages[-1].content
    assert "REVISION REQUESTED" in revision_prompt and "Name the source" in revision_prompt
    sources = task.output["result"]["sources"]
    assert sources["sources"] and "registry_name" in sources["sources"][0]


def test_iteration_limit_escalates_and_retry_is_bounded(db_session, org):
    world, ctx = org
    task = _investigation(db_session, world, ctx)
    world.llm.script("context_agent", osc.context_output(), reusable=True)
    world.llm.script("org_critic", osc.critique("REVISE", ["Still unclear."]), reusable=True)
    engine.run_task(ctx, task.id)
    assert task.status == OrgTaskStatus.ESCALATED
    step = db_session.scalar(
        select(OrgTaskStep).where(OrgTaskStep.task_id == task.id, OrgTaskStep.step_key == "context")
    )
    assert step.iterations == AGENTS["context_agent"].max_iterations == 3
    assert step.escalation["condition"] == "ITERATION_LIMIT"
    assert len(world.llm.calls_for("context_agent")) == 3

    engine.retry(db_session, task.id, world.submitter, "Provider fixed; try again.")
    engine.run_task(ctx, task.id)
    assert task.status == OrgTaskStatus.ESCALATED
    with pytest.raises(Conflict):
        engine.retry(db_session, task.id, world.submitter, "again")
    assert len(world.llm.calls_for("context_agent")) == 6  # hard ceiling, no runaway loop


def test_task_budget_is_enforced(db_session, org, monkeypatch):
    world, ctx = org
    monkeypatch.setattr(engine, "MAX_EXECUTIONS_PER_TASK", 3)
    task = _investigation(db_session, world, ctx)
    engine.run_task(ctx, task.id)
    assert task.status == OrgTaskStatus.ESCALATED and "TASK_BUDGET" in task.escalation_reason
    assert task.executions_used == 3


def test_token_limit_escalates_before_any_llm_call(db_session, org, monkeypatch):
    world, ctx = org
    task = _investigation(db_session, world, ctx)
    import dataclasses

    small = dataclasses.replace(AGENTS["context_agent"], max_input_tokens=10)
    monkeypatch.setitem(AGENTS, "context_agent", small)
    engine.run_task(ctx, task.id)
    assert task.status == OrgTaskStatus.ESCALATED and "TOKEN_LIMIT" in task.escalation_reason
    assert world.llm.calls_for("context_agent") == []


def test_tool_permissions_are_enforced(db_session, org):
    _world, ctx = org
    tc = ToolContext(session=db_session, pipeline=ctx, agent=AGENTS["analytics_agent"])
    with pytest.raises(PermissionDenied):
        tc.call("run_claim_pipeline", claim_id=uuid.uuid4())
    sneaky = AgentDefinition(
        **{**AGENTS["analytics_agent"].__dict__, "tools": ("run_claim_pipeline",)}
    )
    tc = ToolContext(session=db_session, pipeline=ctx, agent=sneaky)
    with pytest.raises(PermissionDenied, match="RUN_PIPELINE"):
        tc.call("run_claim_pipeline", claim_id=uuid.uuid4())
    assert [c["ok"] for c in tc.calls] == [False]


# --- narrative response (human approval) -------------------------------------------------


def _response_task(db_session, world, ctx, languages=("hi",)):
    nid = osc.correctable_narrative(db_session, ctx, world)
    world.llm.script("response_strategist", osc.strategy, reusable=True)
    world.llm.script("org_critic", osc.critique("PASS"), reusable=True)
    world.llm.script("localization_agent", osc.translation, reusable=True)
    return engine.create_task(
        db_session,
        world.submitter,
        WorkflowType.NARRATIVE_RESPONSE,
        {"narrative_id": str(nid), "languages": list(languages)},
    )


def test_narrative_response_needs_human_approval_and_never_publishes(db_session, org):
    world, ctx = org
    task = _response_task(db_session, world, ctx)
    world.llm.script("content_agent", osc.content())
    engine.run_task(ctx, task.id)
    assert task.status == OrgTaskStatus.AWAITING_APPROVAL, task.escalation_reason
    steps = {
        s.step_key: s
        for s in db_session.scalars(select(OrgTaskStep).where(OrgTaskStep.task_id == task.id))
    }
    assert steps["narrative"].output["recommendation"] == "CORRECT"
    assert steps["strategy"].output["format"] == "CORRECTION"
    assert steps["compliance"].output["passed"] is True
    hi = steps["localization"].output["translations"][0]
    assert hi["language"] == "hi" and "81.2" in hi["sentences"][0]["text"]

    with pytest.raises(Forbidden):  # creator cannot approve their own task
        engine.approve(db_session, task.id, world.submitter, None)
    analyst = make_user(db_session, UserRole.ANALYST)
    with pytest.raises(Forbidden):  # analysts cannot approve public-facing work
        engine.approve(db_session, task.id, analyst, None)
    engine.approve(db_session, task.id, world.reviewer, "Checked against F1.")
    assert task.status == OrgTaskStatus.COMPLETED
    draft = task.output["result"]["content"]
    assert draft["ai_assisted_label"] == policy.AI_ASSISTED_LABEL
    assert "published" not in str(task.output).lower()


def test_no_public_response_skips_content_steps(db_session, org):
    world, ctx = org
    osc.script_pipeline(world)
    from app.narratives.engine import run_engine
    from app.pipeline import orchestrator

    for _ in range(2):
        orchestrator.process_submission(ctx, osc.submit(db_session, world).id)
    run_engine(db_session)
    from app.models import Narrative

    nid = db_session.scalar(select(Narrative.id))
    world.llm.script("response_strategist", osc.strategy, reusable=True)
    world.llm.script("org_critic", osc.critique("PASS"), reusable=True)
    task = engine.create_task(
        db_session,
        world.submitter,
        WorkflowType.NARRATIVE_RESPONSE,
        {"narrative_id": str(nid), "languages": ["hi"]},
    )
    engine.run_task(ctx, task.id)
    assert task.status == OrgTaskStatus.AWAITING_APPROVAL
    statuses = {
        s.step_key: s.status
        for s in db_session.scalars(select(OrgTaskStep).where(OrgTaskStep.task_id == task.id))
    }
    assert (
        statuses["content"]
        == statuses["localization"]
        == statuses["compliance"]
        == (StepStatus.SKIPPED)
    )
    assert world.llm.calls_for("content_agent") == []


def test_invented_number_is_rejected_by_content_validation(db_session, org):
    world, ctx = org
    task = _response_task(db_session, world, ctx, languages=())
    bad = osc.content(text="Literacy reached 95 percent in 2023.")  # 95 is in no fact
    world.llm.script("content_agent", bad, reusable=True)
    engine.run_task(ctx, task.id)
    assert task.status == OrgTaskStatus.ESCALATED
    assert "INVALID_OUTPUT" in task.escalation_reason
    assert "95" in task.escalation_reason or "numbers" in task.escalation_reason


def test_compliance_violation_blocks_then_human_revision_fixes(db_session, org):
    world, ctx = org
    task = _response_task(db_session, world, ctx, languages=())
    world.llm.script(
        "content_agent",
        osc.content(
            text="Official statistics put literacy at 81.2 percent in 2023, so vote for change."
        ),
    )
    engine.run_task(ctx, task.id)
    assert task.status == OrgTaskStatus.ESCALATED
    assert "COMPLIANCE_VIOLATION" in task.escalation_reason
    gate = db_session.scalar(
        select(OrgTaskStep).where(
            OrgTaskStep.task_id == task.id, OrgTaskStep.step_key == "compliance"
        )
    )
    assert gate.output["violations"][0]["rule"] == "call_to_vote"
    with pytest.raises(Conflict):
        engine.approve(db_session, task.id, world.reviewer, None)

    engine.request_revision(
        db_session,
        task.id,
        world.reviewer,
        "content",
        "Remove the call to vote; keep to the facts.",
    )
    world.llm.script("content_agent", osc.content())
    engine.run_task(ctx, task.id)
    assert task.status == OrgTaskStatus.AWAITING_APPROVAL
    assert (
        "Remove the call to vote" in world.llm.calls_for("content_agent")[-1].messages[-1].content
    )

    engine.request_revision(db_session, task.id, world.reviewer, "content", "Shorter.")
    world.llm.script("content_agent", osc.content())
    engine.run_task(ctx, task.id)
    with pytest.raises(Conflict, match="Revision limit"):
        engine.request_revision(db_session, task.id, world.reviewer, "content", "Again.")
    engine.reject(db_session, task.id, world.reviewer, "Not needed after all.")
    assert task.status == OrgTaskStatus.REJECTED


def test_strategist_cannot_override_the_engine_recommendation(db_session, org):
    world, ctx = org
    nid = osc.correctable_narrative(db_session, ctx, world)
    world.llm.script(
        "response_strategist",
        StrategyOutput(
            posture="IGNORE", objectives=[], key_messages=[], format="NONE"
        ).model_dump_json(),
        reusable=True,
    )
    task = engine.create_task(
        db_session,
        world.submitter,
        WorkflowType.NARRATIVE_RESPONSE,
        {"narrative_id": str(nid), "languages": []},
    )
    engine.run_task(ctx, task.id)
    assert task.status == OrgTaskStatus.ESCALATED and "INVALID_OUTPUT" in task.escalation_reason


def test_unsupported_language_is_refused(db_session, org):
    world, _ = org
    from app.services.errors import Unprocessable

    with pytest.raises(Unprocessable):
        engine.create_task(
            db_session,
            world.submitter,
            WorkflowType.NARRATIVE_RESPONSE,
            {"narrative_id": str(uuid.uuid4()), "languages": ["xx"]},
        )


# --- analytics and organization view -----------------------------------------------------


def test_analytics_report_is_aggregate_only(db_session, org):
    world, ctx = org
    task = engine.create_task(
        db_session, world.submitter, WorkflowType.ANALYTICS_REPORT, {"window_days": 30}
    )
    engine.run_task(ctx, task.id)
    assert task.status == OrgTaskStatus.COMPLETED
    out = task.output["result"]["analytics"]
    assert set(out) == {
        "window_days",
        "claims_by_classification",
        "review_backlog",
        "narratives_by_recommendation",
        "narrative_trend",
        "agent_executions",
    }


def test_org_chart_shows_status_current_task_performance_and_activity(db_session, settings, org):
    world, ctx = org
    task = _investigation(db_session, world, ctx)
    world.llm.script("context_agent", osc.context_output(), reusable=True)
    world.llm.script("org_critic", osc.critique("REVISE", ["Still unclear."]), reusable=True)
    engine.run_task(ctx, task.id)  # escalates at the context step
    chart = org_chart(db_session, settings)
    nodes = {n["id"]: n for n in chart["nodes"]}
    assert len(nodes) == 15 and nodes["human_oversight"]["kind"] == "HUMAN"
    assert len(chart["edges"]) == 14
    ctx_node = nodes["context_agent"]
    assert ctx_node["status"] == "ESCALATED"
    assert ctx_node["current_task"]["task_id"] == str(task.id)
    assert ctx_node["manager"] == "fact_check_agent"
    assert ctx_node["performance"]["executions"] == 3
    assert ctx_node["performance"]["revision_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert ctx_node["recent_activity"][0]["kind"] in ("ESCALATION", "REVISION")
    assert nodes["critic_agent"]["performance"]["reviews_given"] == 3
    assert nodes["critic_agent"]["performance"]["pipeline_runs"] >= 1  # Phase 1 critic
    assert nodes[CHIEF]["direct_reports"] == sorted(
        k for k, a in AGENTS.items() if a.manager == CHIEF
    )
    assert nodes["research_agent"]["status"] == "IDLE"
    states = agent_states(db_session, settings)
    assert states["claim_extraction_agent"]["performance"]["pipeline_runs"] >= 1
    detail = task_detail(db_session, task.id)
    assert [s["step_key"] for s in detail["steps"]] == [
        "research",
        "sources",
        "context",
        "fact_check",
    ]
    assert detail["steps"][2]["status"] == "ESCALATED"
    assert db_session.scalar(select(func.count()).select_from(OrgExecution)) == len(
        detail["executions"]
    )
