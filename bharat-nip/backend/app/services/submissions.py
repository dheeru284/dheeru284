"""Claim submission (FR-1): text, URL, article, image, PDF, video metadata."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.domain.enums import ActorType, SubmissionType
from app.models import Entity, StoredFile, Submission, User
from app.services.errors import NotFound, Unprocessable


class VideoMetadata(BaseModel):
    """Metadata only: the platform never downloads video. A transcript, if available,
    must be supplied by the submitter."""

    platform: str = Field(min_length=1, max_length=100)
    video_url: HttpUrl | None = None
    title: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=10_000)
    uploader: str | None = Field(default=None, max_length=300)
    published_at: datetime | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    transcript: str | None = Field(default=None, max_length=20_000)

    @model_validator(mode="after")
    def _has_text(self) -> VideoMetadata:
        if not any([self.title, self.description, self.transcript]):
            raise ValueError("Video metadata needs at least a title, description or transcript.")
        return self


class SubmissionInput(BaseModel):
    submission_type: SubmissionType
    raw_text: str | None = Field(default=None, max_length=20_000)
    source_url: HttpUrl | None = None
    title: str | None = Field(default=None, max_length=1000)
    publisher_name: str | None = Field(default=None, max_length=300)
    published_at: datetime | None = None
    language: str = Field(default="en", max_length=10)
    context_note: str | None = Field(default=None, max_length=5000)
    speaker_entity_id: uuid.UUID | None = None
    statement_date: date | None = None
    video: VideoMetadata | None = None

    @model_validator(mode="after")
    def _type_requirements(self) -> SubmissionInput:
        t = self.submission_type
        if t in (SubmissionType.TEXT, SubmissionType.ARTICLE) and not (
            self.raw_text and self.raw_text.strip()
        ):
            raise ValueError(f"{t.value} submissions need raw_text.")
        if t == SubmissionType.URL and not self.source_url:
            raise ValueError("URL submissions need source_url.")
        if t == SubmissionType.VIDEO_METADATA and self.video is None:
            raise ValueError("VIDEO_METADATA submissions need video metadata.")
        return self


FILE_TYPES = {
    SubmissionType.IMAGE: ("image/png", "image/jpeg", "image/gif", "image/webp"),
    SubmissionType.PDF: ("application/pdf",),
}


def create_submission(
    session: Session,
    user: User,
    data: SubmissionInput,
    *,
    stored_file: StoredFile | None = None,
    idempotency_key: str | None = None,
) -> tuple[Submission, bool]:
    """Returns (submission, created). A repeated idempotency key returns the original."""
    if idempotency_key:
        existing = session.scalar(
            select(Submission).where(
                Submission.submitted_by_id == user.id,
                Submission.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing, False

    if data.submission_type in FILE_TYPES:
        if stored_file is None:
            raise Unprocessable(f"{data.submission_type.value} submissions need a file upload.")
        if stored_file.content_type not in FILE_TYPES[data.submission_type]:
            raise Unprocessable(
                f"Uploaded file is {stored_file.content_type}, which does not match "
                f"{data.submission_type.value}."
            )
    elif stored_file is not None:
        raise Unprocessable(f"{data.submission_type.value} submissions do not take a file.")

    if data.speaker_entity_id and session.get(Entity, data.speaker_entity_id) is None:
        raise NotFound("Speaker entity not found.")

    metadata: dict[str, Any] = {}
    if data.video is not None:
        metadata["video"] = data.video.model_dump(mode="json")

    submission = Submission(
        submitted_by_id=user.id,
        submission_type=data.submission_type,
        raw_text=data.raw_text,
        source_url=str(data.source_url) if data.source_url else None,
        title=data.title or (data.video.title if data.video else None),
        publisher_name=data.publisher_name,
        published_at=data.published_at,
        metadata_=metadata,
        file_id=stored_file.id if stored_file else None,
        language=data.language,
        context_note=data.context_note,
        speaker_entity_id=data.speaker_entity_id,
        statement_date=data.statement_date,
        idempotency_key=idempotency_key,
    )
    session.add(submission)
    session.flush()
    AuditService(session).record(
        actor_type=ActorType.USER,
        actor_id=str(user.id),
        action="submission.created",
        entity_type="submission",
        entity_id=submission.id,
        payload={
            "submission_type": data.submission_type.value,
            "source_url": submission.source_url,
            "file_sha256": stored_file.sha256 if stored_file else None,
            "has_text": bool(data.raw_text),
        },
    )
    return submission, True
