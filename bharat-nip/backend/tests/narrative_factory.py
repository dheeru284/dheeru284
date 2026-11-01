"""Builders for narrative tests: claims with controlled times and origins, and human-approved
fact-checks. All content is fictional (Riverland does not exist)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.domain.enums import (
    ClaimStatus,
    ClaimType,
    Classification,
    ProducedBy,
    RecommendedAction,
    ReviewDecisionType,
    ReviewReason,
    ReviewTaskStatus,
    SubmissionType,
)
from app.models import Assessment, Claim, ReviewDecision, ReviewTask, Submission, User

NOW = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)

BRIDGE = [  # a false narrative that keeps coming back
    "The new Riverland river bridge collapsed in March",
    "Riverland river bridge collapsed in March after opening",
    "The Riverland river bridge has collapsed in March",
    "New river bridge in Riverland collapsed in March",
]
LITERACY = [  # an accurate claim
    "Riverland literacy rate rose to 81 percent in 2023",
    "Literacy in Riverland rose to 81 percent in 2023",
]
POLLING = [  # electoral-process misinformation (potential harm)
    "Polling booths in Riverland close at 3 pm on election day",
    "Riverland polling booths will close at 3 pm on election day",
]
UNRELATED = "Riverland tea exports doubled in the last decade"


def make_claim(
    session: Session,
    user: User,
    text: str,
    *,
    seen_at: datetime,
    origin_url: str | None = None,
    publisher: str | None = None,
    claim_type: ClaimType = ClaimType.FACTUAL,
    entities: list[dict] | None = None,
    speaker_text: str = "[SPEAKER] said that",
) -> Claim:
    sub = Submission(
        submitted_by_id=user.id,
        submission_type=SubmissionType.TEXT,
        raw_text=text,
        source_url=origin_url,
        publisher_name=publisher,
        published_at=seen_at,
    )
    session.add(sub)
    session.flush()
    words = text.split()
    claim = Claim(
        submission_id=sub.id,
        text=text,
        normalized_text=f"{speaker_text} {text}",
        subject=" ".join(words[:4]),
        predicate="states",
        object_=" ".join(words[4:]) or text,
        claim_type=claim_type,
        checkworthy=claim_type == ClaimType.FACTUAL,
        language="en",
        entities=entities or [],
        original_source={"submission_id": str(sub.id)},
        status=ClaimStatus.PENDING_REVIEW,
        created_by_id=user.id,
        extracted_at=seen_at,
    )
    session.add(claim)
    session.flush()
    return claim


def approve(
    session: Session,
    claim: Claim,
    reviewer: User,
    classification: Classification,
    confidence: float = 0.8,
    decided_at: datetime | None = None,
) -> ReviewDecision:
    a = Assessment(
        claim_id=claim.id,
        revision=0,
        classification=classification,
        confidence=confidence,
        summary="Fictional test assessment.",
        reasoning="Fictional test assessment.",
        recommended_action=RecommendedAction.CONFIRM_IN_REVIEW,
        produced_by=ProducedBy.RULE,
    )
    session.add(a)
    session.flush()
    task = ReviewTask(
        claim_id=claim.id,
        assessment_id=a.id,
        reason=ReviewReason.ROUTINE,
        priority=4,
        status=ReviewTaskStatus.DECIDED,
    )
    session.add(task)
    session.flush()
    decision = ReviewDecision(
        review_task_id=task.id,
        reviewer_id=reviewer.id,
        decision=ReviewDecisionType.APPROVE,
        final_classification=classification,
    )
    session.add(decision)
    claim.status = ClaimStatus.APPROVED
    session.flush()
    if decided_at:
        decision.created_at = decided_at
        session.flush()
    return decision


def days_ago(n: float) -> datetime:
    return NOW - timedelta(days=n)
