"""Narrative API tests, including an end-to-end run on top of the Phase 1 pipeline:
three submissions of the same (fictional) claim -> pipeline -> narrative detected ->
reviewer approves a fact-check -> evidence status and recommendation update -> analyst
records aggregate observations and responses -> graph, history, timeline, audit."""

import json

from sqlalchemy import select

from app.models import Claim
from tests import scenario as sc

API = "/api/v1"


def _script_reusable(world):
    world.llm.script("claim_extractor", sc.extraction_response(), reusable=True)
    world.search.script([sc.stats_hit(), sc.news_hit()])
    world.llm.script("evidence_analyst", sc.evidence_response, reusable=True)

    # The assessor proposes MOSTLY_TRUE; in the test the reviewer overrides it to FALSE with
    # notes (a valid human decision), which is what the narrative layer must follow.
    world.llm.script("assessor", sc.assessment_response("MOSTLY_TRUE", 0.8), reusable=True)
    world.llm.script("fact_check_critic", sc.critic_response("PASS"), reusable=True)


def _submit(api, headers, n):
    for i in range(n):
        r = api.post(
            f"{API}/submissions",
            headers=headers,
            json={
                "submission_type": "TEXT",
                "raw_text": sc.SUBMISSION_TEXT,
                "source_url": f"https://outlet{i}.example.com/story",
                "published_at": f"2024-03-0{i + 2}T10:00:00Z",
            },
        )
        assert r.status_code == 201, r.text


def test_narrative_end_to_end(api, db_session):
    world = api.world
    _script_reusable(world)
    analyst, reviewer, admin = (
        api.login(u) for u in (world.submitter, world.reviewer, world.admin)
    )
    _submit(api, analyst, 3)

    dash = api.get(f"{API}/narratives", headers=analyst).json()
    assert len(dash["items"]) == 1
    item = dash["items"][0]
    nid = item["id"]
    assert item["status"] == "EMERGING" and item["origin"] == "DETECTED"
    assert item["metrics"]["claim_count"] == 3
    assert item["metrics"]["evidence_status"] == "PENDING_VERIFICATION"
    assert item["metrics"]["details"]["public_interest_indicators"]["distinct_origins"] == 3
    assert dash["counts"]["by_status"]["EMERGING"] == 1
    assert "Asha Verma" not in json.dumps(dash)  # speaker never appears

    # A reviewer approves one fact-check; the review route refreshes the narrative layer.
    tasks = api.get(f"{API}/review-tasks", headers=reviewer).json()
    task = tasks[0]
    r = api.post(
        f"{API}/review-tasks/{task['id']}/decision",
        headers=reviewer,
        json={
            "decision": "APPROVE",
            "final_classification": "FALSE",
            "notes": "Reviewer override in this fictional scenario.",
        },
    )
    assert r.status_code == 201, r.text
    detail = api.get(f"{API}/narratives/{nid}", headers=analyst).json()
    assert detail["metrics"]["evidence_status"] == "VERIFIED_FALSE"
    assert detail["metrics"]["recommendation"] in ("MONITOR", "CORRECT")
    assert "MONITOR" in detail["allowed_status_transitions"]

    # Aggregate public counts and an existing response.
    r = api.post(
        f"{API}/narratives/{nid}/observations",
        headers=analyst,
        json={
            "observed_at": "2024-03-05T00:00:00Z",
            "channel": "video-site",
            "metric": "VIEWS",
            "value": 250000,
            "source_url": "https://video.example.com/stats",
        },
    )
    assert r.status_code == 201
    r = api.post(
        f"{API}/narratives/{nid}/responses",
        headers=analyst,
        json={
            "response_type": "FACT_CHECK",
            "title": "Our fact-check",
            "published_at": "2024-03-06T00:00:00Z",
        },
    )
    assert r.status_code == 201
    assert api.post(f"{API}/narratives/analyze", headers=analyst).status_code == 202
    detail = api.get(f"{API}/narratives/{nid}", headers=analyst).json()
    assert detail["observations"][0]["value"] == 250000
    assert detail["responses"][0]["response_type"] == "FACT_CHECK"
    assert detail["metrics"]["details"]["public_interest_indicators"]["reach"] == 250000
    assert detail["metrics"]["coverage"] >= 0.6

    # Harm assessment and a human status change.
    r = api.put(
        f"{API}/narratives/{nid}/harm",
        headers=analyst,
        json={"category": "OTHER", "severity": "LOW", "rationale": "Minor confusion."},
    )
    assert r.status_code == 200
    bad = api.put(
        f"{API}/narratives/{nid}/harm",
        headers=analyst,
        json={"category": "PUBLIC_SAFETY", "severity": "HIGH"},
    )
    assert bad.status_code == 422
    r = api.post(
        f"{API}/narratives/{nid}/status",
        headers=analyst,
        json={"status": "CORRECT", "note": "Fact-check published; correcting."},
    )
    assert r.status_code == 200 and r.json()["status"] == "CORRECT"
    r = api.post(
        f"{API}/narratives/{nid}/status",
        headers=analyst,
        json={"status": "EMERGING", "note": "not allowed"},
    )
    assert r.status_code == 409

    # Claim history, evidence timeline, metrics history, graph, historical matching.
    history = api.get(f"{API}/narratives/{nid}/claims", headers=analyst).json()
    assert len(history) == 3 and {h["origin"] for h in history} == {
        "outlet0.example.com",
        "outlet1.example.com",
        "outlet2.example.com",
    }
    assert sum(1 for h in history if h["approved_classification"] == "FALSE") == 1
    timeline = api.get(f"{API}/narratives/{nid}/evidence-timeline", headers=analyst).json()
    kinds = {e["kind"] for e in timeline}
    assert kinds == {"EVIDENCE", "REVIEW_DECISION"}
    # Each scenario quote appears once, listing every claim it supports.
    evidence_events = [e for e in timeline if e["kind"] == "EVIDENCE"]
    assert len({(e["source"]["title"], e["quote"]) for e in evidence_events}) == len(
        evidence_events
    )
    assert all(len(e["claim_ids"]) == 3 for e in evidence_events)
    assert timeline == sorted(timeline, key=lambda e: (e["at"], e["kind"]))
    series = api.get(f"{API}/narratives/{nid}/metrics", headers=analyst).json()
    assert len(series) >= 2 and series[-1]["version"] > series[0]["version"]
    g = api.get(f"{API}/narratives/graph", headers=analyst).json()
    assert [n["id"] for n in g["nodes"]] == [nid]
    latest_claim = history[-1]["claim_id"]
    matches = api.get(f"{API}/claims/{latest_claim}/history", headers=analyst).json()
    assert len(matches) == 2 and all(m["narrative_id"] == nid for m in matches)
    assert any(m["approved_classification"] == "FALSE" for m in matches)
    topics = api.get(f"{API}/topics", headers=analyst).json()
    assert topics and topics[0]["claim_count"] >= 3

    # Everything is audited and the chain still verifies.
    events = api.get(
        f"{API}/audit-events", headers=admin, params={"entity_id": nid, "limit": 500}
    ).json()
    actions = {e["action"] for e in events}
    for a in (
        "narrative.created",
        "narrative.recommendation_changed",
        "narrative.observation_added",
        "narrative.response_recorded",
        "narrative.harm_assessed",
        "narrative.status_changed",
    ):
        assert a in actions, a
    assert api.get(f"{API}/audit-events/verify", headers=admin).json()["ok"]


def test_manual_narrative_membership_and_validation(api, db_session):
    world = api.world
    _script_reusable(world)
    analyst = api.login(world.submitter)
    _submit(api, analyst, 1)
    claim_id = str(db_session.scalar(select(Claim.id)))

    r = api.post(
        f"{API}/narratives",
        headers=analyst,
        json={"claim_ids": [claim_id], "title": "Analyst-defined narrative"},
    )
    assert r.status_code == 201
    nid = r.json()["id"]
    assert (
        api.post(f"{API}/narratives", headers=analyst, json={"claim_ids": [claim_id]}).status_code
        == 409
    )
    r = api.post(
        f"{API}/narratives/{nid}/claims/{claim_id}/remove",
        headers=analyst,
        json={"note": "Wrong grouping."},
    )
    assert r.status_code == 200 and r.json()["excluded"]
    r = api.post(
        f"{API}/narratives/{nid}/claims",
        headers=analyst,
        json={"claim_id": claim_id, "note": "Re-added after review."},
    )
    assert r.status_code == 201
    r = api.patch(f"{API}/narratives/{nid}", headers=analyst, json={"summary": "Context."})
    assert r.json()["summary"] == "Context."
    obs = api.post(
        f"{API}/narratives/{nid}/observations",
        headers=analyst,
        json={
            "observed_at": "2024-03-05T00:00:00Z",
            "channel": "x",
            "metric": "VIEWS",
            "value": -1,
        },
    )
    assert obs.status_code == 422


def test_narrative_endpoints_require_analyst_role(api, db_session):
    from app.domain.enums import UserRole
    from app.services.users import create_user

    submitter = create_user(
        db_session,
        email="sub@test.example",
        display_name="S",
        role=UserRole.SUBMITTER,
        password=sc.PASSWORD,
        created_by=None,
    )
    h = api.login(submitter)
    for path in ("/narratives", "/narratives/graph", "/topics"):
        assert api.get(f"{API}{path}", headers=h).status_code == 403
    assert api.post(f"{API}/narratives/analyze", headers=h).status_code == 403
    assert api.get(f"{API}/narratives").status_code == 401


def test_observation_schema_accepts_no_personal_fields(api):
    """Aggregate only: unknown fields such as a user handle are rejected by schema design
    (they are simply not part of the model and never stored)."""
    from app.api.routes.narratives import ObservationIn

    assert set(ObservationIn.model_fields) == {
        "observed_at",
        "channel",
        "metric",
        "value",
        "source_url",
        "note",
    }
