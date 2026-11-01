from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, str_enum, updated_at_col, uuid_pk
from app.domain.enums import (
    ClaimStatus,
    ClaimType,
    EntityType,
    ExtractionMethod,
    SubmissionStatus,
    SubmissionType,
)

MAX_SUBMISSION_CHARS = 20_000
MAX_EXTRACTED_CHARS = 200_000


class Entity(Base):
    """A public speaker or organization. Never a private citizen (SECURITY.md §5)."""

    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(300))
    entity_type: Mapped[EntityType] = mapped_column(str_enum(EntityType, 30, "entity_type"))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class StoredFile(Base):
    """An uploaded file (image, PDF). Bytes live in BNIP_STORAGE_DIR, addressed by sha256."""

    __tablename__ = "stored_files"

    id: Mapped[uuid.UUID] = uuid_pk()
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_path: Mapped[str] = mapped_column(String(500))
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        CheckConstraint(
            f"raw_text IS NULL OR char_length(raw_text) <= {MAX_SUBMISSION_CHARS}",
            name="raw_text_length",
        ),
        CheckConstraint(
            f"extracted_text IS NULL OR char_length(extracted_text) <= {MAX_EXTRACTED_CHARS}",
            name="extracted_text_length",
        ),
        UniqueConstraint(
            "submitted_by_id", "idempotency_key", name="uq_submissions_submitter_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    submitted_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    submission_type: Mapped[SubmissionType] = mapped_column(
        str_enum(SubmissionType, 20, "submission_type")
    )
    # What the user typed or pasted (text, article body, caption, transcript).
    raw_text: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    title: Mapped[str | None] = mapped_column(String(1000))
    publisher_name: Mapped[str | None] = mapped_column(String(300))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Video metadata and other type-specific fields.
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("stored_files.id"))
    language: Mapped[str] = mapped_column(String(10), server_default="en", default="en")
    context_note: Mapped[str | None] = mapped_column(Text)
    speaker_entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entities.id"))
    statement_date: Mapped[date | None] = mapped_column(Date)
    idempotency_key: Mapped[str | None] = mapped_column(String(100))
    # The machine-readable text that claim extraction runs on, and how it was obtained.
    extracted_text: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[ExtractionMethod | None] = mapped_column(
        str_enum(ExtractionMethod, 30, "extraction_method")
    )
    extraction_notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SubmissionStatus] = mapped_column(
        str_enum(SubmissionStatus, 30, "status"), default=SubmissionStatus.RECEIVED
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
    subject: Mapped[str] = mapped_column(Text)
    predicate: Mapped[str] = mapped_column(Text)
    object_: Mapped[str] = mapped_column("object", Text)
    # As stated in the claim ("in 2023", "last quarter"), plus a resolved date if possible.
    time_reference: Mapped[str | None] = mapped_column(Text)
    claim_date: Mapped[date | None] = mapped_column(Date)
    location: Mapped[str | None] = mapped_column(Text)
    # [{"name", "type", "role"}]; role SPEAKER entities are blinded out of normalized_text.
    entities: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # {"submission_id", "submission_type", "url", "title", "publisher"}
    original_source: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
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
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
