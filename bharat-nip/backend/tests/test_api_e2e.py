"""END-TO-END over HTTP: submit -> extract -> evidence -> assess -> critic -> human
review -> audit trail, using MockLLMProvider and MockSearchProvider only."""

from tests import scenario as sc

API = "/api/v1"


def test_end_to_end_over_the_api(api):
    world = api.world
    sc.script_happy_path(world, revise_first=True)
    submitter = api.login(world.submitter)
    reviewer = api.login(world.reviewer)
    admin = api.login(world.admin)

    # Submit (pipeline runs inline in tests; on a Celery worker in production)
    r = api.post(
        f"{API}/submissions",
        json={
            "submission_type": "TEXT",
            "raw_text": sc.SUBMISSION_TEXT,
            "speaker_entity_id": str(world.speaker.id),
            "statement_date": "2024-03-02",
        },
        headers={**submitter, "Idempotency-Key": "e2e-1"},
    )
    assert r.status_code == 201, r.text
    submission_id = r.json()["submission"]["id"]

    # Same idempotency key -> the original submission, not a new one
    again = api.post(
        f"{API}/submissions",
        json={"submission_type": "TEXT", "raw_text": "different"},
        headers={**submitter, "Idempotency-Key": "e2e-1"},
    )
    assert again.status_code == 200 and again.json()["submission"]["id"] == submission_id

    detail = api.get(f"{API}/submissions/{submission_id}", headers=submitter).json()
    assert detail["submission"]["status"] == "PROCESSED"
    assert detail["submission"]["extraction_method"] == "USER_TEXT"
    [claim] = detail["claims"]
    for field in (
        "id",
        "text",
        "subject",
        "predicate",
        "object",
        "time_reference",
        "location",
        "entities",
        "original_source",
        "extracted_at",
    ):
        assert claim[field] is not None, field
    assert claim["review_status"] == "PENDING_REVIEW"
    stages = [j["stage"] for j in detail["pipeline_jobs"]]
    assert stages == ["CONTENT", "EXTRACTION"]
    claim_id = claim["id"]

    claim_detail = api.get(f"{API}/claims/{claim_id}", headers=submitter).json()
    claim_stages = [j["stage"] for j in claim_detail["pipeline_jobs"]]
    assert claim_stages[:3] == ["SEARCH", "EVIDENCE", "RANKING"]
    assert claim_stages.count("ASSESSMENT") == 2 and claim_stages.count("CRITIQUE") == 2
    assert all(j["status"] == "SUCCEEDED" for j in claim_detail["pipeline_jobs"])

    # Structured result (analysts can see it before review)
    fc = api.get(f"{API}/claims/{claim_id}/fact-check", headers=submitter).json()
    assert fc["classification"] == "MOSTLY_TRUE"
    assert isinstance(fc["confidence"], float)
    assert fc["supporting_evidence"] and fc["contradicting_evidence"] == []
    assert fc["recommended_action"] == "CONFIRM_IN_REVIEW"
    assert fc["review_status"] == "PENDING_REVIEW"

    evidence = api.get(f"{API}/claims/{claim_id}/evidence", headers=submitter).json()
    assert len(evidence) == 2
    assert all(e["source"]["content_sha256"] and e["rank_components"] for e in evidence)
    searches = api.get(f"{API}/claims/{claim_id}/searches", headers=submitter).json()
    assert searches and all(s["provider"] == "mock" for s in searches)
    assessments = api.get(f"{API}/claims/{claim_id}/assessments", headers=submitter).json()
    assert [a["revision"] for a in assessments] == [0, 1]
    assert assessments[0]["critiques"][0]["outcome"] == "REVISE"

    # Human review: the submitter (an analyst) cannot decide
    tasks = api.get(f"{API}/review-tasks", headers=reviewer).json()
    [task] = [t for t in tasks if t["claim_id"] == claim_id]
    assert task["proposed_classification"] == "MOSTLY_TRUE" and not task["submitted_by_me"]
    forbidden = api.post(
        f"{API}/review-tasks/{task['id']}/decision",
        json={"decision": "APPROVE"},
        headers=submitter,
    )
    assert forbidden.status_code == 403
    # Changing the classification without notes is refused
    bad = api.post(
        f"{API}/review-tasks/{task['id']}/decision",
        json={"decision": "APPROVE", "final_classification": "TRUE"},
        headers=reviewer,
    )
    assert bad.status_code == 422
    ok = api.post(
        f"{API}/review-tasks/{task['id']}/decision",
        json={"decision": "APPROVE", "notes": "Checked the bulletin myself."},
        headers=reviewer,
    )
    assert ok.status_code == 201, ok.text
    twice = api.post(
        f"{API}/review-tasks/{task['id']}/decision",
        json={"decision": "REJECT", "notes": "x"},
        headers=reviewer,
    )
    assert twice.status_code == 409

    fc = api.get(f"{API}/claims/{claim_id}/fact-check", headers=submitter).json()
    assert fc["review_status"] == "APPROVED" and fc["final_classification"] == "MOSTLY_TRUE"

    # Audit trail for the claim, then whole-chain verification
    trail = api.get(f"{API}/claims/{claim_id}/audit", headers=submitter).json()
    actions = [e["action"] for e in trail]
    for required in (
        "claim.extracted",
        "search.executed",
        "evidence.created",
        "assessment.created",
        "assessment.revised",
        "critique.created",
        "review_task.created",
        "review.decided",
        "ai_run.recorded",
    ):
        assert required in actions, required
    agents = {e["actor_id"] for e in trail if e["action"] == "ai_run.recorded"}
    assert agents == {"claim_extractor", "evidence_analyst", "assessor", "fact_check_critic"}
    assert actions.index("claim.extracted") < actions.index("review.decided")
    verify = api.get(f"{API}/audit-events/verify", headers=admin).json()
    assert verify["ok"] and verify["checked"] > 20

    run_id = fc["provenance"]["ai_run_id"]
    run = api.get(f"{API}/ai-runs/{run_id}", headers=submitter).json()
    assert run["agent_name"] == "assessor" and run["provider"] == "mock"
    assert run["prompt_id"] == "assessor" and run["prompt_version"] == "v1"


def test_reviewer_cannot_approve_their_own_submission(api):
    world = api.world
    world.llm.script("claim_extractor", sc.extraction_response())
    world.search.script([])
    reviewer = api.login(world.reviewer)
    r = api.post(
        f"{API}/submissions",
        json={"submission_type": "TEXT", "raw_text": sc.SUBMISSION_TEXT},
        headers=reviewer,
    )
    claim_id = api.get(
        f"{API}/submissions/{r.json()['submission']['id']}", headers=reviewer
    ).json()["claims"][0]["id"]
    [task] = [
        t
        for t in api.get(f"{API}/review-tasks", headers=reviewer).json()
        if t["claim_id"] == claim_id
    ]
    assert task["submitted_by_me"]
    r = api.post(
        f"{API}/review-tasks/{task['id']}/decision", json={"decision": "APPROVE"}, headers=reviewer
    )
    assert r.status_code == 403
    assert "four-eyes" in r.json()["detail"]
