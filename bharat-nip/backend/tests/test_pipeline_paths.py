"""Pipeline behaviour on the paths that matter for trustworthiness."""

import json

from sqlalchemy import select

from app.domain.enums import (
    AIRunStatus,
    ClaimStatus,
    Classification,
    ProducedBy,
    ReviewDecisionType,
    ReviewReason,
    SubmissionType,
)
from app.models import AIRun, Assessment, AuditEvent, Claim, Critique, Evidence, ReviewTask
from app.pipeline import orchestrator
from app.services import review
from app.services.factcheck import build_fact_check
from app.services.submissions import SubmissionInput, create_submission
from tests import scenario as sc


def submit(db_session, world, text=sc.SUBMISSION_TEXT, speaker=True):
    sub, _ = create_submission(
        db_session,
        world.submitter,
        SubmissionInput(
            submission_type=SubmissionType.TEXT,
            raw_text=text,
            speaker_entity_id=world.speaker.id if speaker else None,
        ),
    )
    return sub


def run(db_session, settings, world, **kw):
    ctx = sc.make_context(db_session, settings, world)
    [claim_id] = orchestrator.process_submission(ctx, submit(db_session, world, **kw).id)
    return db_session.get(Claim, claim_id)


def task_for(db_session, claim):
    return db_session.scalar(
        select(ReviewTask).where(ReviewTask.claim_id == claim.id, ReviewTask.status == "OPEN")
    )


def test_no_evidence_gives_insufficient_evidence_without_llm(db_session, settings):
    world = sc.make_world(db_session)
    world.llm.script("claim_extractor", sc.extraction_response())
    world.search.script([])  # nothing found
    claim = run(db_session, settings, world)

    a = db_session.scalar(select(Assessment).where(Assessment.claim_id == claim.id))
    assert a.classification == Classification.INSUFFICIENT_EVIDENCE
    assert a.produced_by == ProducedBy.RULE and a.ai_run_id is None
    assert a.confidence == 0.0
    assert world.llm.calls_for("assessor") == []
    assert world.llm.calls_for("evidence_analyst") == []
    assert task_for(db_session, claim).reason == ReviewReason.INSUFFICIENT_EVIDENCE
    assert claim.status == ClaimStatus.PENDING_REVIEW


def test_opinion_is_not_fact_checked(db_session, settings):
    world = sc.make_world(db_session)
    world.llm.script(
        "claim_extractor",
        sc.extraction_response(
            text="Riverland's schools are the best in the world.", claim_type="OPINION"
        ),
    )
    claim = run(
        db_session,
        settings,
        world,
        text="Minister Asha Verma said Riverland's schools are the best in the world.",
    )
    a = db_session.scalar(select(Assessment).where(Assessment.claim_id == claim.id))
    assert a.classification == Classification.OPINION
    assert a.recommended_action.value == "NOT_FACT_CHECKABLE"
    assert world.search.queries == []  # no research for non-checkable claims
    assert claim.status == ClaimStatus.PENDING_REVIEW


def test_revision_loop_is_bounded(db_session, settings):
    world = sc.make_world(db_session)
    world.llm.script("claim_extractor", sc.extraction_response())
    world.search.script([sc.stats_hit(), sc.news_hit()])
    world.llm.script("evidence_analyst", sc.evidence_response)
    world.llm.script("assessor", sc.assessment_response(), reusable=True)
    world.llm.script(
        "fact_check_critic", sc.critic_response("REVISE", ("missing_context",)), reusable=True
    )
    claim = run(db_session, settings, world)

    n = settings.max_revision_rounds
    revisions = db_session.scalars(
        select(Assessment.revision).where(Assessment.claim_id == claim.id)
    ).all()
    assert sorted(revisions) == list(range(n + 1))  # first assessment + n revisions
    assert len(world.llm.calls_for("fact_check_critic")) == n + 1
    assert task_for(db_session, claim).reason == ReviewReason.LOOP_LIMIT


def test_critic_pass_is_overridden_when_contradicting_evidence_was_ignored(db_session, settings):
    world = sc.make_world(db_session)
    world.llm.script("claim_extractor", sc.extraction_response())
    world.search.script([sc.stats_hit(), sc.news_hit()])

    def evidence(request):
        items = json.loads(sc.evidence_response(request))["items"]
        items[0]["stance"] = "REFUTES"  # the official bulletin contradicts the claim
        items[0]["rationale"] = "Bulletin contradicts the claim (test scenario)."
        return json.dumps({"items": items})

    world.llm.script("evidence_analyst", evidence)

    def assess(request):  # cite only the SUPPORTS item, ignore the REFUTES one
        content = request.messages[-1].content
        support = "E1" if "Stance: SUPPORTS" in content.split("<<<EVIDENCE id=E2>>>")[0] else "E2"
        return sc.assessment_response("TRUE", 0.9, cited=(support,))

    world.llm.script("assessor", assess)
    world.llm.script("fact_check_critic", sc.critic_response("PASS"))
    claim = run(db_session, settings, world)

    a = db_session.scalar(select(Assessment).where(Assessment.claim_id == claim.id))
    rules = {g["rule"] for g in a.guardrails}
    assert "strong_contrary_evidence" in rules and a.confidence <= 0.5
    critique = db_session.scalar(select(Critique))
    assert critique.agent_outcome.value == "PASS"
    assert critique.outcome.value == "ESCALATE" and critique.outcome_overridden
    assert task_for(db_session, claim).reason == ReviewReason.RULE_FLAG


def test_fabricated_quote_is_rejected(db_session, settings):
    world = sc.make_world(db_session)
    world.llm.script("claim_extractor", sc.extraction_response())
    world.search.script([sc.stats_hit()])
    world.llm.script(
        "evidence_analyst",
        lambda req: json.dumps(
            {
                "items": [
                    {
                        "chunk": sc.passage_label(req, sc.STATS_QUOTE),
                        # Not in the source: a fabricated figure.
                        "quote": "the state literacy rate was 95 percent in 2023",
                        "stance": "SUPPORTS",
                        "directness": "DIRECT",
                        "relevance": 0.9,
                        "rationale": "fabricated",
                    }
                ]
            }
        ),
    )
    claim = run(db_session, settings, world)
    assert db_session.scalars(select(Evidence)).all() == []
    rejected = db_session.scalars(
        select(AuditEvent).where(AuditEvent.action == "evidence.rejected")
    ).all()
    assert rejected and rejected[0].payload["reason"] == "quote not found verbatim in the passage"
    a = db_session.scalar(select(Assessment).where(Assessment.claim_id == claim.id))
    assert a.classification == Classification.INSUFFICIENT_EVIDENCE


def test_invalid_citation_is_retried_then_accepted(db_session, settings):
    world = sc.make_world(db_session)
    sc.script_happy_path(world, revise_first=False)
    world.llm._scripts = [s for s in world.llm._scripts if s.prompt_id != "assessor"]
    world.llm.script("assessor", sc.assessment_response(cited=("E9",)))  # unknown label
    world.llm.script("assessor", sc.assessment_response())
    run(db_session, settings, world)
    statuses = db_session.scalars(
        select(AIRun.status).where(AIRun.agent_name == "assessor").order_by(AIRun.attempt)
    ).all()
    assert statuses == [AIRunStatus.INVALID_OUTPUT, AIRunStatus.SUCCEEDED]
    retry = world.llm.calls_for("assessor")[1]
    assert "previous output was invalid" in retry.messages[-1].content


def test_stage_failure_goes_to_human_and_keeps_the_failed_ai_run(db_session, settings):
    world = sc.make_world(db_session)
    world.llm.script("claim_extractor", sc.extraction_response())
    world.search.script([sc.stats_hit(), sc.news_hit()])
    world.llm.script("evidence_analyst", sc.evidence_response)
    # assessor deliberately not scripted -> provider failure
    claim = run(db_session, settings, world)
    task = task_for(db_session, claim)
    assert task.reason == ReviewReason.STAGE_FAILURE and "ASSESSMENT" in task.reason_detail
    assert claim.status == ClaimStatus.PENDING_REVIEW
    failed = db_session.scalars(select(AIRun).where(AIRun.status == AIRunStatus.FAILED)).all()
    assert failed and failed[0].agent_name == "assessor"


def test_needs_more_research_then_rerun_creates_new_revision(db_session, settings):
    world = sc.make_world(db_session)
    world.llm.script("claim_extractor", sc.extraction_response())
    world.search.script([])
    claim = run(db_session, settings, world)
    review.decide(
        db_session,
        task_for(db_session, claim).id,
        world.reviewer,
        ReviewDecisionType.NEEDS_MORE_RESEARCH,
        None,
        "Check the statistics office bulletin.",
    )
    assert claim.status == ClaimStatus.NEEDS_MORE_RESEARCH

    # New material becomes findable; the analyst re-runs research.
    world.search._rules.clear()
    world.search.script([sc.stats_hit(), sc.news_hit()])
    world.llm.script("evidence_analyst", sc.evidence_response)
    world.llm.script("assessor", sc.assessment_response())
    world.llm.script("fact_check_critic", sc.critic_response("PASS"))
    orchestrator.process_claim(sc.make_context(db_session, settings, world), claim.id)

    revs = db_session.scalars(
        select(Assessment).where(Assessment.claim_id == claim.id).order_by(Assessment.revision)
    ).all()
    assert [a.classification for a in revs] == [
        Classification.INSUFFICIENT_EVIDENCE,
        Classification.TRUE,
    ]
    assert revs[0].status.value == "SUPERSEDED"
    assert claim.status == ClaimStatus.PENDING_REVIEW
    assert build_fact_check(db_session, claim)["classification"] == "TRUE"


def test_ungrounded_extracted_claim_is_rejected(db_session, settings):
    world = sc.make_world(db_session)
    world.llm.script(
        "claim_extractor",
        sc.extraction_response(text="Neighbouring Hillstate banned all imports of steel."),
    )
    ctx = sc.make_context(db_session, settings, world)
    claim_ids = orchestrator.process_submission(ctx, submit(db_session, world).id)
    assert claim_ids == []
    ev = db_session.scalar(select(AuditEvent).where(AuditEvent.action == "claim.rejected"))
    assert "not grounded" in ev.payload["reason"]
