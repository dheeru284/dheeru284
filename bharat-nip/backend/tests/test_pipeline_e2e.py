"""END-TO-END (service level): submitted claim -> extracted claim -> evidence ->
assessment -> critic (with one revision) -> human review -> audit trail.
Uses only MockLLMProvider and MockSearchProvider: no network, no paid API."""

from sqlalchemy import func, select

from app.audit.service import AuditService
from app.domain.enums import (
    AIRunStatus,
    ClaimStatus,
    Classification,
    ReviewDecisionType,
    ReviewReason,
    SubmissionType,
)
from app.models import (
    AIRun,
    Assessment,
    AuditEvent,
    Claim,
    Critique,
    Evidence,
    ReviewTask,
    SearchQuery,
    Source,
)
from app.pipeline import orchestrator
from app.services import review
from app.services.factcheck import build_fact_check
from app.services.submissions import SubmissionInput, create_submission
from tests import scenario as sc


def test_full_pipeline_with_revision_and_human_approval(db_session, settings):
    world = sc.make_world(db_session)
    sc.script_happy_path(world, revise_first=True)
    ctx = sc.make_context(db_session, settings, world)

    # 1. Submission
    sub, created = create_submission(
        db_session,
        world.submitter,
        SubmissionInput(
            submission_type=SubmissionType.TEXT,
            raw_text=sc.SUBMISSION_TEXT,
            speaker_entity_id=world.speaker.id,
        ),
    )
    assert created

    # 2-7. Pipeline (content, extraction, search, evidence, ranking, assessment, critic)
    claim_ids = orchestrator.process_submission(ctx, sub.id)
    assert len(claim_ids) == 1
    claim = db_session.get(Claim, claim_ids[0])

    # Extraction: structured, blinded claim
    assert claim.subject == "Riverland's literacy rate"
    assert claim.predicate == "rose to"
    assert claim.object_ == "81 percent in 2023"
    assert claim.time_reference == "2023" and claim.location == "Riverland"
    assert {e["role"] for e in claim.entities} == {"SPEAKER", "SUBJECT"}
    assert claim.original_source["submission_id"] == str(sub.id)
    assert claim.extracted_at is not None
    assert sc.SPEAKER_NAME not in claim.normalized_text
    assert "[SPEAKER]" in claim.normalized_text

    # Search never saw the speaker's identity
    assert world.search.queries
    assert all(sc.SPEAKER_NAME not in q for q in world.search.queries)

    # Evidence: verbatim slices of stored, hashed sources
    evidence = db_session.scalars(select(Evidence).where(Evidence.claim_id == claim.id)).all()
    assert len(evidence) == 2
    for ev in evidence:
        src = db_session.get(Source, ev.source_id)
        assert src.content_text[ev.quote_char_start : ev.quote_char_end] == ev.quote
        assert len(src.content_sha256) == 64
        assert 0 <= ev.relevance <= 1
    stats_src = db_session.scalar(select(Source).where(Source.url == sc.STATS_URL))
    assert stats_src.is_primary and stats_src.registry_source_id is not None

    # Assessment was revised once after the critic asked for it
    assessments = db_session.scalars(
        select(Assessment).where(Assessment.claim_id == claim.id).order_by(Assessment.revision)
    ).all()
    assert [a.revision for a in assessments] == [0, 1]
    assert assessments[0].status.value == "SUPERSEDED"
    final = assessments[1]
    assert final.classification == Classification.MOSTLY_TRUE
    assert final.parent_assessment_id == assessments[0].id
    critiques = db_session.scalars(select(Critique).order_by(Critique.created_at)).all()
    assert [c.outcome.value for c in critiques] == ["REVISE", "PASS"]
    # The revision prompt carried the critic's objections to the assessor
    assessor_calls = world.llm.calls_for("assessor")
    assert "REVISION REQUESTED" in assessor_calls[1].messages[-1].content

    # Human review is pending; no agent approved anything
    assert claim.status == ClaimStatus.PENDING_REVIEW
    task = db_session.scalar(select(ReviewTask).where(ReviewTask.claim_id == claim.id))
    assert task.reason == ReviewReason.ROUTINE

    # 8. Human review (a different person than the submitter)
    review.decide(db_session, task.id, world.reviewer, ReviewDecisionType.APPROVE, None, None)
    db_session.commit()
    assert claim.status == ClaimStatus.APPROVED

    # 9. Structured fact-check result
    result = build_fact_check(db_session, claim)
    for key in (
        "classification",
        "confidence",
        "summary",
        "reasoning",
        "supporting_evidence",
        "contradicting_evidence",
        "missing_information",
        "recommended_action",
    ):
        assert key in result
    assert result["classification"] == "MOSTLY_TRUE"
    assert 0 <= result["confidence"] <= 1
    assert len(result["supporting_evidence"]) == 2
    assert result["contradicting_evidence"] == []
    assert result["review_status"] == "APPROVED"
    assert result["final_classification"] == "MOSTLY_TRUE"
    assert result["review_decision"]["decision"] == "APPROVE"
    assert result["review_decision"]["reviewer_id"] == str(world.reviewer.id)
    assert result["provenance"]["provider"] == "mock"
    assert result["provenance"]["prompt_version"] == "v1"
    assert result["critic"]["outcome"] == "PASS"
    first = result["supporting_evidence"][0]
    assert {
        "url",
        "title",
        "publisher",
        "published_at",
        "retrieved_at",
        "source_type",
        "content_sha256",
    } <= first["source"].keys()

    # 10. Every agent execution recorded with provider/model/prompt version and hash
    runs = db_session.scalars(select(AIRun)).all()
    assert {r.agent_name for r in runs} == {
        "claim_extractor",
        "evidence_analyst",
        "assessor",
        "fact_check_critic",
    }
    assert all(r.status == AIRunStatus.SUCCEEDED for r in runs)
    assert all(
        r.provider == "mock" and r.prompt_version == "v1" and len(r.prompt_sha256) == 64
        for r in runs
    )
    # The assessor and critic never saw the speaker's name.
    for call in world.llm.calls_for("assessor") + world.llm.calls_for("fact_check_critic"):
        assert all(sc.SPEAKER_NAME not in m.content for m in call.messages)

    # 11. Audit trail covers every step, and the hash chain verifies
    actions = set(db_session.scalars(select(AuditEvent.action)))
    for required in (
        "submission.created",
        "submission.content_extracted",
        "claim.extracted",
        "search.executed",
        "source.created",
        "evidence.created",
        "evidence.ranked",
        "ai_run.recorded",
        "assessment.created",
        "assessment.revised",
        "critique.created",
        "review_task.created",
        "review.decided",
        "claim.status_changed",
    ):
        assert required in actions, required
    db_session.expire_all()
    chain = AuditService(db_session).verify_chain()
    assert chain.ok, chain
    assert chain.checked == db_session.scalar(select(func.count()).select_from(AuditEvent))
    assert db_session.scalar(select(func.count()).select_from(SearchQuery)) >= 1
