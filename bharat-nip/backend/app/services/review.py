"""Human review (FR-9). Only humans decide; nobody decides on their own submission."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.domain.enums import (
    ActorType,
    AssessmentStatus,
    ClaimStatus,
    Classification,
    ReviewDecisionType,
    ReviewReason,
    ReviewTaskStatus,
    UserRole,
)
from app.domain.state import assert_transition
from app.models import Assessment, Claim, ReviewDecision, ReviewTask, Submission, User
from app.services.errors import Conflict, Forbidden, NotFound, Unprocessable

PRIORITY = {
    ReviewReason.CRITIC_ESCALATION: 1,
    ReviewReason.RULE_FLAG: 1,
    ReviewReason.STAGE_FAILURE: 1,
    ReviewReason.LOOP_LIMIT: 2,
    ReviewReason.LOW_CONFIDENCE: 2,
    ReviewReason.INSUFFICIENT_EVIDENCE: 3,
    ReviewReason.ROUTINE: 4,
}


def set_claim_status(session: Session, claim: Claim, target: ClaimStatus, actor: str) -> None:
    assert_transition(claim.status, target)
    previous = claim.status
    claim.status = target
    session.flush()
    AuditService(session).record(
        actor_type=ActorType.USER if not actor.startswith("system:") else ActorType.SYSTEM,
        actor_id=actor,
        action="claim.status_changed",
        entity_type="claim",
        entity_id=claim.id,
        payload={"from": previous.value, "to": target.value},
    )


def route_to_review(
    session: Session,
    claim: Claim,
    assessment: Assessment | None,
    reason: ReviewReason,
    detail: str | None = None,
) -> ReviewTask:
    # Cancel any older open task for this claim: one open task per claim.
    for old in session.scalars(
        select(ReviewTask).where(
            ReviewTask.claim_id == claim.id, ReviewTask.status == ReviewTaskStatus.OPEN
        )
    ):
        old.status = ReviewTaskStatus.CANCELLED
    task = ReviewTask(
        claim_id=claim.id,
        assessment_id=assessment.id if assessment else None,
        reason=reason,
        reason_detail=detail,
        priority=PRIORITY[reason],
        status=ReviewTaskStatus.OPEN,
    )
    session.add(task)
    if assessment is not None:
        assessment.status = AssessmentStatus.PENDING_REVIEW
    set_claim_status(session, claim, ClaimStatus.PENDING_REVIEW, "system:review_routing")
    AuditService(session).record(
        actor_type=ActorType.SYSTEM,
        actor_id="system:review_routing",
        action="review_task.created",
        entity_type="review_task",
        entity_id=task.id,
        payload={
            "claim_id": str(claim.id),
            "assessment_id": str(assessment.id) if assessment else None,
            "reason": reason.value,
            "detail": detail,
            "priority": task.priority,
        },
    )
    return task


def decide(
    session: Session,
    task_id: uuid.UUID,
    reviewer: User,
    decision: ReviewDecisionType,
    final_classification: Classification | None,
    notes: str | None,
) -> ReviewDecision:
    if reviewer.role not in (UserRole.REVIEWER, UserRole.ADMIN):
        raise Forbidden("Only reviewers can decide review tasks.")
    task = session.get(ReviewTask, task_id, with_for_update=True)
    if task is None:
        raise NotFound("Review task not found.")
    if task.status != ReviewTaskStatus.OPEN:
        raise Conflict(f"Review task is {task.status.value}.")
    claim = session.get(Claim, task.claim_id)
    submission = session.get(Submission, claim.submission_id)
    if submission.submitted_by_id == reviewer.id:
        raise Forbidden("You cannot review a claim from your own submission (four-eyes rule).")
    assessment = session.get(Assessment, task.assessment_id) if task.assessment_id else None
    notes = (notes or "").strip() or None

    if decision == ReviewDecisionType.APPROVE:
        if assessment is None:
            raise Unprocessable("Nothing to approve: this task has no assessment.")
        final_classification = final_classification or assessment.classification
        if final_classification != assessment.classification and not notes:
            raise Unprocessable("Changing the classification requires notes.")
        target, a_status = ClaimStatus.APPROVED, AssessmentStatus.APPROVED
    elif decision == ReviewDecisionType.REJECT:
        if not notes:
            raise Unprocessable("Rejecting requires notes.")
        target, a_status = ClaimStatus.REJECTED, AssessmentStatus.REJECTED
        final_classification = None
    else:
        if not notes:
            raise Unprocessable("Requesting more research requires notes on what is missing.")
        target, a_status = ClaimStatus.NEEDS_MORE_RESEARCH, AssessmentStatus.NEEDS_MORE_RESEARCH
        final_classification = None

    row = ReviewDecision(
        review_task_id=task.id,
        reviewer_id=reviewer.id,
        decision=decision,
        final_classification=final_classification,
        notes=notes,
    )
    session.add(row)
    task.status = ReviewTaskStatus.DECIDED
    task.assigned_to_id = reviewer.id
    if assessment is not None:
        assessment.status = a_status
    set_claim_status(session, claim, target, str(reviewer.id))
    AuditService(session).record(
        actor_type=ActorType.USER,
        actor_id=str(reviewer.id),
        action="review.decided",
        entity_type="review_task",
        entity_id=task.id,
        payload={
            "claim_id": str(claim.id),
            "assessment_id": str(assessment.id) if assessment else None,
            "decision": decision.value,
            "proposed_classification": assessment.classification.value if assessment else None,
            "final_classification": final_classification.value if final_classification else None,
            "classification_changed": bool(
                assessment
                and final_classification
                and final_classification != assessment.classification
            ),
            "notes": notes,
        },
    )
    return row
