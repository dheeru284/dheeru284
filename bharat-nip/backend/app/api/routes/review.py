from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import Reviewer
from app.api.deps import get_db
from app.domain.enums import ReviewReason, ReviewTaskStatus
from app.models import Assessment, Claim, ReviewTask, Submission
from app.schemas.api import DecisionIn, DecisionOut, ReviewTaskOut
from app.services import review as review_service
from app.services.errors import NotFound

router = APIRouter(tags=["review"])
DB = Annotated[Session, Depends(get_db)]


def _task_out(db: Session, task: ReviewTask, user_id: uuid.UUID) -> ReviewTaskOut:
    out = ReviewTaskOut.model_validate(task)
    claim = db.get(Claim, task.claim_id)
    out.claim_text = claim.text
    out.submitted_by_me = db.get(Submission, claim.submission_id).submitted_by_id == user_id
    if task.assessment_id:
        a = db.get(Assessment, task.assessment_id)
        out.proposed_classification = a.classification
        out.proposed_confidence = a.confidence
    return out


@router.get("/review-tasks", response_model=list[ReviewTaskOut])
def list_tasks(
    user: Reviewer,
    db: DB,
    status: ReviewTaskStatus = ReviewTaskStatus.OPEN,
    reason: ReviewReason | None = None,
):
    q = (
        select(ReviewTask)
        .where(ReviewTask.status == status)
        .order_by(ReviewTask.priority, ReviewTask.created_at)
    )
    if reason:
        q = q.where(ReviewTask.reason == reason)
    return [_task_out(db, t, user.id) for t in db.scalars(q.limit(200))]


@router.get("/review-tasks/{task_id}", response_model=ReviewTaskOut)
def get_task(task_id: uuid.UUID, user: Reviewer, db: DB):
    task = db.get(ReviewTask, task_id)
    if task is None:
        raise NotFound("Review task not found.")
    return _task_out(db, task, user.id)


@router.post("/review-tasks/{task_id}/decision", response_model=DecisionOut, status_code=201)
def decide(task_id: uuid.UUID, body: DecisionIn, user: Reviewer, db: DB):
    decision = review_service.decide(
        db, task_id, user, body.decision, body.final_classification, body.notes
    )
    db.commit()
    return decision
