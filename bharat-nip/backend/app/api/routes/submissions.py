from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.access import can_see_all, get_visible_submission, require_result_visible
from app.api.auth import CurrentUser
from app.api.deps import get_db, get_dispatcher, get_settings_dep
from app.api.serializers import claim_out, claims_for_submission, submission_out
from app.audit.service import AuditService
from app.core.config import Settings
from app.domain.enums import ActorType, ClaimStatus, SubmissionStatus
from app.models import PipelineJob, Submission
from app.pipeline.dispatch import PipelineDispatcher
from app.schemas.api import (
    Page,
    PipelineJobOut,
    SubmissionCreated,
    SubmissionDetail,
    SubmissionOut,
    TranscriptionIn,
    decode_cursor,
    encode_cursor,
)
from app.services.errors import Conflict, Unprocessable
from app.services.storage import save_upload
from app.services.submissions import SubmissionInput, create_submission

router = APIRouter(tags=["submissions"])
DB = Annotated[Session, Depends(get_db)]
Dispatcher = Annotated[PipelineDispatcher, Depends(get_dispatcher)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=100)]


def _created(db: Session, sub: Submission, created: bool, dispatcher: PipelineDispatcher):
    db.commit()
    if created:
        dispatcher.submit(sub.id)
        db.refresh(sub)
    body = SubmissionCreated(submission=submission_out(sub), created=created)
    return JSONResponse(status_code=201 if created else 200, content=body.model_dump(mode="json"))


@router.post("/submissions", response_model=SubmissionCreated, status_code=201)
def submit(
    body: SubmissionInput,
    user: CurrentUser,
    db: DB,
    dispatcher: Dispatcher,
    idempotency_key: IdempotencyKey = None,
):
    """Text, URL, article or video-metadata submission (JSON)."""
    sub, created = create_submission(db, user, body, idempotency_key=idempotency_key)
    return _created(db, sub, created, dispatcher)


@router.post("/submissions/upload", response_model=SubmissionCreated, status_code=201)
def submit_file(
    user: CurrentUser,
    db: DB,
    dispatcher: Dispatcher,
    settings: SettingsDep,
    file: Annotated[UploadFile, File(description="Image or PDF")],
    payload: Annotated[str, Form(description="SubmissionInput as JSON")],
    idempotency_key: IdempotencyKey = None,
):
    """Image or PDF submission (multipart: `file` + `payload` JSON)."""
    try:
        body = SubmissionInput.model_validate(json.loads(payload))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise Unprocessable(f"Invalid payload: {exc}") from exc
    data = file.file.read(settings.max_upload_bytes + 1)
    stored = save_upload(db, settings, user, file.filename or "upload", data)
    sub, created = create_submission(
        db, user, body, stored_file=stored, idempotency_key=idempotency_key
    )
    return _created(db, sub, created, dispatcher)


@router.get("/submissions", response_model=Page[SubmissionOut])
def list_submissions(
    user: CurrentUser,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
    mine: bool = False,
):
    offset = decode_cursor(cursor)
    q = select(Submission).order_by(Submission.created_at.desc(), Submission.id)
    if mine or not can_see_all(user):
        q = q.where(Submission.submitted_by_id == user.id)
    rows = db.scalars(q.offset(offset).limit(limit + 1)).all()
    return Page(
        items=[submission_out(s) for s in rows[:limit]],
        next_cursor=encode_cursor(offset + limit) if len(rows) > limit else None,
    )


@router.get("/submissions/{submission_id}", response_model=SubmissionDetail)
def get_submission(submission_id: uuid.UUID, user: CurrentUser, db: DB):
    sub = get_visible_submission(db, user, submission_id)
    jobs = db.scalars(
        select(PipelineJob)
        .where(PipelineJob.submission_id == sub.id)
        .order_by(PipelineJob.created_at)
    ).all()
    claims = claims_for_submission(db, sub.id)
    return SubmissionDetail(
        submission=submission_out(sub),
        claims=[
            claim_out(db, c, include_result=can_see_all(user) or c.status == ClaimStatus.APPROVED)
            for c in claims
        ],
        pipeline_jobs=[PipelineJobOut.model_validate(j) for j in jobs],
    )


@router.post("/submissions/{submission_id}/transcription", response_model=SubmissionOut)
def add_transcription(
    submission_id: uuid.UUID,
    body: TranscriptionIn,
    user: CurrentUser,
    db: DB,
    dispatcher: Dispatcher,
):
    """Provide a human transcription for an image/PDF without machine-readable text."""
    sub = get_visible_submission(db, user, submission_id)
    if sub.status != SubmissionStatus.NEEDS_TRANSCRIPTION:
        raise Conflict(f"Submission is {sub.status.value}; no transcription is needed.")
    sub.raw_text = body.text
    sub.status = SubmissionStatus.RECEIVED
    AuditService(db).record(
        actor_type=ActorType.USER,
        actor_id=str(user.id),
        action="submission.transcription_added",
        entity_type="submission",
        entity_id=sub.id,
        payload={"chars": len(body.text)},
    )
    db.commit()
    dispatcher.submit(sub.id)
    db.refresh(sub)
    return submission_out(sub)


__all__ = ["require_result_visible", "router"]
