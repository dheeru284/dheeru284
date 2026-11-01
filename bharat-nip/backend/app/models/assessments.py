from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, str_enum, updated_at_col, uuid_pk
from app.domain.enums import AssessmentStatus, Confidence, CriticOutcome, ProducedBy, Verdict


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("claim_id", "revision"),
        CheckConstraint("revision >= 0", name="revision_nonnegative"),
        CheckConstraint(
            "(produced_by = 'RULE' AND ai_run_id IS NULL)"
            " OR (produced_by = 'AGENT' AND ai_run_id IS NOT NULL)",
            name="producer",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    parent_assessment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assessments.id"))
    verdict: Mapped[Verdict] = mapped_column(str_enum(Verdict, 30, "verdict"))
    confidence: Mapped[Confidence] = mapped_column(str_enum(Confidence, 10, "confidence"))
    rationale: Mapped[str] = mapped_column(Text)
    missing_context: Mapped[str | None] = mapped_column(Text)
    produced_by: Mapped[ProducedBy] = mapped_column(str_enum(ProducedBy, 20, "produced_by"))
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_runs.id"))
    status: Mapped[AssessmentStatus] = mapped_column(
        str_enum(AssessmentStatus, 20, "status"), default=AssessmentStatus.DRAFT
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class AssessmentCitation(Base):
    __tablename__ = "assessment_citations"

    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"), primary_key=True)
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    note: Mapped[str | None] = mapped_column(Text)


class Critique(Base):
    __tablename__ = "critiques"

    id: Mapped[uuid.UUID] = uuid_pk()
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"), index=True)
    outcome: Mapped[CriticOutcome] = mapped_column(str_enum(CriticOutcome, 20, "outcome"))
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    summary: Mapped[str] = mapped_column(Text)
    ai_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_runs.id"))
    created_at: Mapped[datetime] = created_at_col()
