from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, str_enum, uuid_pk
from app.domain.enums import Directness, Stance


class Evidence(Base):
    """A verbatim quote from a stored source. ``quote`` must equal
    ``source.content_text[quote_char_start:quote_char_end]``."""

    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint("quote_char_end > quote_char_start", name="quote_range"),
        CheckConstraint(
            "(extracted_by_ai_run_id IS NULL) <> (created_by_id IS NULL)", name="author"
        ),
        CheckConstraint("relevance >= 0 AND relevance <= 1", name="relevance_range"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id"), index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_chunks.id"))
    quote: Mapped[str] = mapped_column(Text)
    quote_char_start: Mapped[int] = mapped_column(Integer)
    quote_char_end: Mapped[int] = mapped_column(Integer)
    # Support / contradiction relationship to the claim.
    stance: Mapped[Stance] = mapped_column(str_enum(Stance, 20, "stance"))
    stance_rationale: Mapped[str] = mapped_column(Text)
    directness: Mapped[Directness] = mapped_column(str_enum(Directness, 20, "directness"))
    # relevance = mean(lexical, agent); both inputs kept for transparency.
    relevance: Mapped[float] = mapped_column(Float)
    lexical_relevance: Mapped[float] = mapped_column(Float)
    agent_relevance: Mapped[float | None] = mapped_column(Float)
    extracted_by_ai_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_runs.id"))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()


class EvidenceRanking(Base):
    __tablename__ = "evidence_rankings"
    __table_args__ = (
        UniqueConstraint("evidence_id", "ranking_version"),
        CheckConstraint("score >= 0 AND score <= 1", name="score_range"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id"))
    ranking_version: Mapped[str] = mapped_column(String(20))
    score: Mapped[float] = mapped_column(Float)
    components: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_col()
