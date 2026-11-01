from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import SCHEMA_EMBEDDING_DIMENSIONS
from app.db.base import Base, created_at_col, str_enum, updated_at_col, uuid_pk
from app.domain.enums import ReliabilityTier, RetrievalMethod, SourceType

EMBEDDING_DIMENSIONS = SCHEMA_EMBEDDING_DIMENSIONS  # nomic-embed-text


class Publisher(Base):
    __tablename__ = "publishers"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(300))
    domain: Mapped[str | None] = mapped_column(String(255), unique=True)
    # Methodology-based tier (DATABASE_DESIGN.md §3.5). Never based on political alignment.
    reliability_tier: Mapped[ReliabilityTier] = mapped_column(
        str_enum(ReliabilityTier, 10, "reliability_tier"),
        server_default=ReliabilityTier.UNRATED.value,
        default=ReliabilityTier.UNRATED,
    )
    tier_rationale: Mapped[str | None] = mapped_column(Text)
    tier_set_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    tier_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Source(Base):
    """Immutable document snapshot. Created only by retrieval providers or human ingest."""

    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = uuid_pk()
    publisher_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("publishers.id"))
    source_type: Mapped[SourceType] = mapped_column(str_enum(SourceType, 30, "source_type"))
    title: Mapped[str] = mapped_column(String(1000))
    url: Mapped[str | None] = mapped_column(String(2048))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retrieval_provider: Mapped[str] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(10))
    content_text: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    ingested_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (
        UniqueConstraint("source_id", "chunk_index"),
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


class RetrievalResult(Base):
    __tablename__ = "retrieval_results"

    id: Mapped[uuid.UUID] = uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id"), index=True)
    chunk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_chunks.id"))
    provider: Mapped[str] = mapped_column(String(50))
    query_text: Mapped[str] = mapped_column(Text)
    method: Mapped[RetrievalMethod] = mapped_column(str_enum(RetrievalMethod, 20, "method"))
    score: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    pipeline_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pipeline_jobs.id"))
    created_at: Mapped[datetime] = created_at_col()
