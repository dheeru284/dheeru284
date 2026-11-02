"""Organization API, end to end over HTTP with the inline dispatcher and scripted mocks."""

from app.domain.enums import UserRole
from app.services.users import create_user
from tests import org_scenario as osc
from tests import scenario as sc

API = "/api/v1/org"


def test_narrative_response_task_over_http(api, db_session):
    world = api.world
    nid = osc.correctable_narrative(db_session, api.ctx, world)
    world.llm.script("response_strategist", osc.strategy, reusable=True)
    world.llm.script("org_critic", osc.critique("PASS"), reusable=True)
    world.llm.script("content_agent", osc.content(), reusable=True)
    world.llm.script("localization_agent", osc.translation, reusable=True)
    analyst, reviewer = api.login(world.submitter), api.login(world.reviewer)

    r = api.post(
        f"{API}/tasks",
        headers=analyst,
        json={
            "workflow": "NARRATIVE_RESPONSE",
            "input": {"narrative_id": str(nid), "languages": ["hi", "ta"]},
        },
    )
    assert r.status_code == 201, r.text
    task = r.json()
    assert task["status"] == "AWAITING_APPROVAL" and task["approval_level"] == "HUMAN"

    detail = api.get(f"{API}/tasks/{task['id']}", headers=analyst).json()
    assert [s["step_key"] for s in detail["steps"]] == [
        "narrative",
        "analytics",
        "strategy",
        "content",
        "localization",
        "compliance",
    ]
    assert all(s["status"] == "DONE" for s in detail["steps"])
    langs = [t["language"] for t in detail["steps"][4]["output"]["translations"]]
    assert langs == ["hi", "ta"]
    kinds = [e["kind"] for e in detail["executions"]]
    assert kinds[:6] == ["DELEGATION"] * 6 and kinds[-1] == "APPROVAL"
    assert {e["step_key"] for e in detail["executions"] if e["kind"] == "EXECUTION"} == {
        "narrative",
        "analytics",
        "strategy",
        "content",
        "localization",
        "compliance",
    }
    llm_execs = [e for e in detail["executions"] if e["ai_run_id"]]
    assert {e["agent_key"] for e in llm_execs} >= {
        "response_strategist",
        "content_agent",
        "localization_agent",
        "critic_agent",
    }
    assert all(e["model"].startswith("mock/") for e in llm_execs)

    # Creator cannot approve; analysts cannot approve; a reviewer can.
    assert (
        api.post(f"{API}/tasks/{task['id']}/approve", headers=analyst, json={}).status_code == 403
    )
    r = api.post(
        f"{API}/tasks/{task['id']}/request-revision",
        headers=reviewer,
        json={"step_key": "narrative", "notes": "Not a revisable step."},
    )
    assert r.status_code == 422
    r = api.post(
        f"{API}/tasks/{task['id']}/approve",
        headers=reviewer,
        json={"notes": "Accurate and proportionate."},
    )
    assert r.status_code == 200 and r.json()["status"] == "COMPLETED"
    detail = api.get(f"{API}/tasks/{task['id']}", headers=analyst).json()
    assert detail["approvals"][-1]["approver_type"] == "HUMAN"
    human_rows = [
        e
        for e in detail["executions"]
        if e["kind"] == "APPROVAL" and e["agent_key"] == "human_reviewer"
    ]
    assert len(human_rows) == 1
    assert detail["output"]["result"]["compliance"]["passed"] is True
    assert (
        api.post(
            f"{API}/tasks/{task['id']}/reject", headers=reviewer, json={"notes": "late"}
        ).status_code
        == 409
    )


def test_agents_chart_workflows_and_internal_task(api, db_session):
    world = api.world
    analyst = api.login(world.submitter)
    agents = api.get(f"{API}/agents", headers=analyst).json()
    assert len(agents) == 14
    one = next(a for a in agents if a["key"] == "content_agent")
    for field in (
        "role",
        "responsibilities",
        "input_schema",
        "output_schema",
        "permissions",
        "tools",
        "model",
        "max_input_tokens",
        "max_output_tokens",
        "max_iterations",
        "escalation_rules",
        "manager",
        "direct_reports",
        "status",
        "performance",
        "recent_activity",
    ):
        assert field in one, field
    assert one["manager"] == "response_strategist"
    assert {r["condition"] for r in one["escalation_rules"]} >= {
        "ITERATION_LIMIT",
        "NO_APPROVED_EVIDENCE",
    }

    r = api.post(
        f"{API}/tasks",
        headers=analyst,
        json={"workflow": "ANALYTICS_REPORT", "input": {"window_days": 7}},
    )
    assert r.json()["status"] == "COMPLETED" and r.json()["approval_level"] == "MANAGER"
    chart = api.get(f"{API}/chart", headers=analyst).json()
    assert len(chart["nodes"]) == 15 and len(chart["edges"]) == 14
    analytics = next(n for n in chart["nodes"] if n["id"] == "analytics_agent")
    assert analytics["performance"]["executions"] == 1
    assert analytics["recent_activity"][0]["task"].startswith("Analytics report")
    wfs = api.get(f"{API}/workflows", headers=analyst).json()
    assert {w["workflow"] for w in wfs if "workflow" in w} == {
        "SUBMISSION_FACT_CHECK",
        "CLAIM_INVESTIGATION",
        "MEDIA_CHECK",
        "NARRATIVE_RESPONSE",
        "ANALYTICS_REPORT",
    }
    tasks = api.get(f"{API}/tasks", headers=analyst).json()
    assert tasks[0]["workflow"] == "ANALYTICS_REPORT"


def test_escalated_task_retry_and_cancel(api, db_session):
    world = api.world
    osc.script_pipeline(world)
    from app.pipeline import orchestrator

    [cid] = orchestrator.process_submission(api.ctx, osc.submit(db_session, world).id)
    world.llm.script("context_agent", osc.context_output(), reusable=True)
    world.llm.script(
        "org_critic", osc.critique("ESCALATE", ["Evidence is contested."]), reusable=True
    )
    analyst = api.login(world.submitter)
    task = api.post(
        f"{API}/tasks",
        headers=analyst,
        json={"workflow": "CLAIM_INVESTIGATION", "input": {"claim_id": str(cid)}},
    ).json()
    assert task["status"] == "ESCALATED" and "REVIEW_ESCALATED" in task["escalation_reason"]
    r = api.post(f"{API}/tasks/{task['id']}/retry", headers=analyst, json={"notes": "Retry."})
    assert r.json()["status"] == "ESCALATED"
    assert (
        api.post(
            f"{API}/tasks/{task['id']}/retry", headers=analyst, json={"notes": "Again."}
        ).status_code
        == 409
    )
    r = api.post(f"{API}/tasks/{task['id']}/cancel", headers=analyst, json={"notes": "Stop."})
    assert r.json()["status"] == "CANCELLED"


def test_org_requires_analyst_and_validates_input(api, db_session):
    sub = create_user(
        db_session,
        email="s2@test.example",
        display_name="S",
        role=UserRole.SUBMITTER,
        password=sc.PASSWORD,
        created_by=None,
    )
    h = api.login(sub)
    assert api.get(f"{API}/chart", headers=h).status_code == 403
    assert (
        api.post(
            f"{API}/tasks", headers=h, json={"workflow": "ANALYTICS_REPORT", "input": {}}
        ).status_code
        == 403
    )
    analyst = api.login(api.world.submitter)
    r = api.post(
        f"{API}/tasks",
        headers=analyst,
        json={"workflow": "CLAIM_INVESTIGATION", "input": {"claim_id": "nope"}},
    )
    assert r.status_code == 422
