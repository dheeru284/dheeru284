from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import UniqueConstraint as UQ
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import SCHEMA_EMBEDDING_DIMENSIONS
from app.db.base import Base, created_at_col, str_enum, updated_at_col, uuid_pk
from app.domain.enums import (
    AuthorityLevel,
    FetchStatus,
    RegistryVerificationStatus,
    SearchStatus,
    SourceCategory,
    SourceType,
)

EMBEDDING_DIMENSIONS = SCHEMA_EMBEDDING_DIMENSIONS  # nomic-embed-text


class RegistrySource(Base):
    """Source registry entry (DATABASE_DESIGN.md §3.5).

    Describes *what kind of source* an origin is, where it has authority, and how that
    was verified. It is deliberately not a true/false list: authority is scoped to a
    jurisdiction and topics, must be justified, and expires (``review_due_at``).
    """

    __tablename__ = "registry_sources"
    __table_args__ = (
        CheckConstraint(
            "authority_level = 'UNASSESSED' OR authority_rationale IS NOT NULL",
            name="authority_rationale_required",
        ),
        CheckConstraint(
            "verification_status <> 'VERIFIED'"
            " OR (verified_by_id IS NOT NULL AND verified_at IS NOT NULL"
            " AND review_due_at IS NOT NULL)",
            name="verification_complete",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(300))
    domain: Mapped[str | None] = mapped_column(String(255), unique=True)
    category: Mapped[SourceCategory] = mapped_column(str_enum(SourceCategory, 40, "category"))
    # ISO 3166 code or subdivision ("IN", "IN-MH") or "GLOBAL".
    jurisdiction: Mapped[str] = mapped_column(String(20))
    authority_level: Mapped[AuthorityLevel] = mapped_column(
        str_enum(AuthorityLevel, 30, "authority_level"),
        server_default=AuthorityLevel.UNASSESSED.value,
        default=AuthorityLevel.UNASSESSED,
    )
    # Topics the authority applies to, e.g. ["census", "population"]. Empty = general.
    authority_scope: Mapped[list[str]] = mapped_column(JSONB, default=list)
    authority_rationale: Mapped[str | None] = mapped_column(Text)
    default_source_type: Mapped[SourceType] = mapped_column(
        str_enum(SourceType, 30, "default_source_type"), default=SourceType.OTHER
    )
    # True when this origin produces primary material (records, data, judgments).
    is_primary_source: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_status: Mapped[RegistryVerificationStatus] = mapped_column(
        str_enum(RegistryVerificationStatus, 20, "verification_status"),
        default=RegistryVerificationStatus.UNVERIFIED,
    )
    verification_method: Mapped[str | None] = mapped_column(Text)
    verification_notes: Mapped[str | None] = mapped_column(Text)
    verified_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Source(Base):
    """Immutable document snapshot. Created only by search/fetch or human ingest."""

    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = uuid_pk()
    registry_source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("registry_sources.id"))
    source_type: Mapped[SourceType] = mapped_column(str_enum(SourceType, 30, "source_type"))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    title: Mapped[str] = mapped_column(String(1000))
    url: Mapped[str | None] = mapped_column(String(2048))
    publisher_name: Mapped[str | None] = mapped_column(String(300))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retrieval_provider: Mapped[str] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(10))
    content_text: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    # How the snapshot was obtained: content_type, final_url, http_status, extractor, ...
    fetch_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    ingested_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (
        UQ("source_id", "chunk_index"),
        CheckConstraint("char_end > char_start", name="char_range"),
        Index("ix_source_chunks_text_search", "text_search", postgresql_using="gin"),
        Index(
            "ix_source_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    text_search: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple'::regconfig, text)", persisted=True)
    )
    created_at: Mapped[datetime] = created_at_col()


class SearchQuery(Base):
    """One query sent to one search provider for one claim."""

    __tablename__ = "search_queries"

    id: Mapped[uuid.UUID] = uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50))
    query_text: Mapped[str] = mapped_column(Text)
    status: Mapped[SearchStatus] = mapped_column(str_enum(SearchStatus, 20, "status"))
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    pipeline_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pipeline_jobs.id"))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()


class SearchResult(Base):
    __tablename__ = "search_results"

    id: Mapped[uuid.UUID] = uuid_pk()
    search_query_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_queries.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    url: Mapped[str | None] = mapped_column(String(2048))
    title: Mapped[str] = mapped_column(String(1000))
    snippet: Mapped[str | None] = mapped_column(Text)
    provider_score: Mapped[float | None] = mapped_column()
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"))
    fetch_status: Mapped[FetchStatus] = mapped_column(str_enum(FetchStatus, 20, "fetch_status"))
    fetch_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
