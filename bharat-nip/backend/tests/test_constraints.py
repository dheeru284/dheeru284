"""Schema-level guarantees (DATABASE_DESIGN.md) verified against real PostgreSQL."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.hashing import sha256_text
from app.domain.enums import (
    ProducedBy,
    ReviewDecisionType,
    ReviewReason,
    SourceType,
    Stance,
    UserRole,
    Verdict,
)
from app.models import (
    Assessment,
    Claim,
    Evidence,
    ReviewDecision,
    ReviewTask,
    Source,
    Submission,
)
from app.models.claims import MAX_SUBMISSION_CHARS
from tests.factories import claim_kwargs, make_human_claim, make_submission, make_user


def expect_integrity_error(session, obj):
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(obj)
        session.flush()


def make_source(session, content="Official data: literacy rose to 80% in 2021."):
    src = Source(
        source_type=SourceType.STATISTICAL_DATA,
        title="Census bulletin",
        retrieved_at=datetime.now(UTC),
        retrieval_provider="human_ingest",
        language="en",
        content_text=content,
        content_sha256=sha256_text(content),
    )
    session.add(src)
    session.flush()
    return src


def test_pgvector_extension_installed(db_session):
    assert db_session.scalar(text("SELECT extname FROM pg_extension WHERE extname='vector'"))


def test_submission_length_limit(db_session):
    user = make_user(db_session)
    expect_integrity_error(
        db_session, Submission(submitted_by_id=user.id, raw_text="x" * (MAX_SUBMISSION_CHARS + 1))
    )


def test_claim_needs_an_author(db_session):
    user = make_user(db_session)
    sub = make_submission(db_session, user)
    orphan = Claim(**claim_kwargs(sub))
    expect_integrity_error(db_session, orphan)


def test_claim_type_check_constraint_rejects_unknown_values(db_session):
    user = make_user(db_session)
    sub = make_submission(db_session, user)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            text(
                "INSERT INTO claims (id, submission_id, text, normalized_text, subject,"
                " predicate, object, entities, original_source, claim_type, checkworthy,"
                " language, status, created_by_id, extracted_at)"
                " VALUES (gen_random_uuid(), :s, 't', 't', 's', 'p', 'o', '[]', '{}',"
                " 'PROPAGANDA', true, 'en', 'EXTRACTED', :u, now())"
            ),
            {"s": sub.id, "u": user.id},
        )


def test_source_content_hash_is_unique(db_session):
    make_source(db_session)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        make_source(db_session)


def test_evidence_needs_exactly_one_author(db_session):
    user = make_user(db_session)
    claim = make_human_claim(db_session, make_submission(db_session, user), user)
    src = make_source(db_session)
    no_author = Evidence(
        claim_id=claim.id,
        source_id=src.id,
        quote="literacy rose",
        quote_char_start=15,
        quote_char_end=28,
        stance=Stance.SUPPORTS,
        stance_rationale="r",
        directness="DIRECT",
        relevance=0.5,
        lexical_relevance=0.5,
    )
    expect_integrity_error(db_session, no_author)


def test_rule_assessment_has_no_ai_run_and_agent_assessment_needs_one(db_session):
    user = make_user(db_session)
    claim = make_human_claim(db_session, make_submission(db_session, user), user)
    ok = Assessment(
        claim_id=claim.id,
        revision=0,
        classification=Verdict.INSUFFICIENT_EVIDENCE,
        confidence=0.0,
        summary="No evidence was found.",
        reasoning="No evidence was found.",
        recommended_action="GATHER_MORE_EVIDENCE",
        produced_by=ProducedBy.RULE,
    )
    db_session.add(ok)
    db_session.flush()
    bad = Assessment(
        claim_id=claim.id,
        revision=1,
        classification=Verdict.TRUE,
        confidence=0.0,
        summary="r",
        reasoning="r",
        recommended_action="GATHER_MORE_EVIDENCE",
        produced_by=ProducedBy.AGENT,
    )
    expect_integrity_error(db_session, bad)


def test_every_verdict_is_accepted_by_the_database(db_session):
    user = make_user(db_session)
    claim = make_human_claim(db_session, make_submission(db_session, user), user)
    for i, verdict in enumerate(Verdict):
        db_session.add(
            Assessment(
                claim_id=claim.id,
                revision=i,
                classification=verdict,
                confidence=0.0,
                summary="r",
                reasoning="r",
                recommended_action="GATHER_MORE_EVIDENCE",
                produced_by=ProducedBy.RULE,
            )
        )
    db_session.flush()


def test_review_decision_rules(db_session):
    submitter = make_user(db_session, UserRole.SUBMITTER)
    reviewer = make_user(db_session, UserRole.REVIEWER)
    claim = make_human_claim(db_session, make_submission(db_session, submitter), submitter)
    assessment = Assessment(
        claim_id=claim.id,
        revision=0,
        classification=Verdict.INSUFFICIENT_EVIDENCE,
        confidence=0.0,
        summary="r",
        reasoning="r",
        recommended_action="GATHER_MORE_EVIDENCE",
        produced_by=ProducedBy.RULE,
    )
    db_session.add(assessment)
    db_session.flush()
    task = ReviewTask(
        claim_id=claim.id,
        assessment_id=assessment.id,
        reason=ReviewReason.INSUFFICIENT_EVIDENCE,
        priority=1,
    )
    db_session.add(task)
    db_session.flush()

    # NEEDS_MORE_RESEARCH needs notes.
    expect_integrity_error(
        db_session,
        ReviewDecision(
            review_task_id=task.id,
            reviewer_id=reviewer.id,
            decision=ReviewDecisionType.NEEDS_MORE_RESEARCH,
            final_classification=Verdict.UNVERIFIED,
        ),
    )
    # APPROVE needs a final verdict.
    expect_integrity_error(
        db_session,
        ReviewDecision(
            review_task_id=task.id, reviewer_id=reviewer.id, decision=ReviewDecisionType.APPROVE
        ),
    )
    good = ReviewDecision(
        review_task_id=task.id,
        reviewer_id=reviewer.id,
        decision=ReviewDecisionType.APPROVE,
        final_classification=Verdict.INSUFFICIENT_EVIDENCE,
    )
    db_session.add(good)
    db_session.flush()
    # One decision per task.
    expect_integrity_error(
        db_session,
        ReviewDecision(
            review_task_id=task.id,
            reviewer_id=reviewer.id,
            decision=ReviewDecisionType.REJECT,
            notes="dup",
        ),
    )
