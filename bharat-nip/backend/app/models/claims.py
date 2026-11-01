from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, str_enum, updated_at_col, uuid_pk
from app.domain.enums import ClaimStatus, ClaimType, EntityType, SubmissionStatus

MAX_SUBMISSION_CHARS = 20_000


class Entity(Base):
    """A public speaker or organization. Never a private citizen (SECURITY.md §5)."""

    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(300))
    entity_type: Mapped[EntityType] = mapped_column(str_enum(EntityType, 30, "entity_type"))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        CheckConstraint(f"char_length(raw_text) <= {MAX_SUBMISSION_CHARS}", name="raw_text_length"),
        UniqueConstraint(
            "submitted_by_id", "idempotency_key", name="uq_submissions_submitter_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    submitted_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    raw_text: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    language: Mapped[str] = mapped_column(String(10), server_default="en", default="en")
    context_note: Mapped[str | None] = mapped_column(Text)
    speaker_entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entities.id"))
    statement_date: Mapped[date | None] = mapped_column(Date)
    idempotency_key: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[SubmissionStatus] = mapped_column(
        str_enum(SubmissionStatus, 20, "status"), default=SubmissionStatus.RECEIVED
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint(
            "extraction_ai_run_id IS NOT NULL OR created_by_id IS NOT NULL", name="author"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    # Blinded form: the only text the assessor and critic ever see.
    normalized_text: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[ClaimType] = mapped_column(str_enum(ClaimType, 20, "claim_type"))
    checkworthy: Mapped[bool] = mapped_column(Boolean)
    language: Mapped[str] = mapped_column(String(10))
    # Attribution only. Never passed to assessment prompts.
    speaker_entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entities.id"))
    statement_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[ClaimStatus] = mapped_column(
        str_enum(ClaimStatus, 30, "status"), default=ClaimStatus.EXTRACTED, index=True
    )
    extraction_ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_runs.id")
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
