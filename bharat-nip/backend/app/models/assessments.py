from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, str_enum, updated_at_col, uuid_pk
from app.domain.enums import (
    AssessmentStatus,
    Classification,
    CriticOutcome,
    ProducedBy,
    RecommendedAction,
)


class Assessment(Base):
    """A fact-check result for a claim. Each revision is a new row."""

    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("claim_id", "revision"),
        CheckConstraint("revision >= 0", name="revision_nonnegative"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
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
    classification: Mapped[Classification] = mapped_column(
        str_enum(Classification, 30, "classification")
    )
    # Evidence-based confidence in the classification, after calibration caps.
    confidence: Mapped[float] = mapped_column(Float)
    # What the agent proposed before caps (null for RULE assessments).
    confidence_raw: Mapped[float | None] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text)
    missing_information: Mapped[list[str]] = mapped_column(JSONB, default=list)
    recommended_action: Mapped[RecommendedAction] = mapped_column(
        str_enum(RecommendedAction, 30, "recommended_action")
    )
    # Deterministic guardrails that fired: [{"rule", "detail"}].
    guardrails: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    produced_by: Mapped[ProducedBy] = mapped_column(str_enum(ProducedBy, 20, "produced_by"))
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_runs.id"))
    status: Mapped[AssessmentStatus] = mapped_column(
        str_enum(AssessmentStatus, 30, "status"), default=AssessmentStatus.DRAFT
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class AssessmentCitation(Base):
    __tablename__ = "assessment_citations"

    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"), primary_key=True)
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    note: Mapped[str | None] = mapped_column(Text)


class Critique(Base):
    """Output of the FactCheckCriticAgent plus deterministic findings."""

    __tablename__ = "critiques"

    id: Mapped[uuid.UUID] = uuid_pk()
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"), index=True)
    # Final outcome after rule overrides; agent_outcome is what the critic proposed.
    outcome: Mapped[CriticOutcome] = mapped_column(str_enum(CriticOutcome, 20, "outcome"))
    agent_outcome: Mapped[CriticOutcome] = mapped_column(
        str_enum(CriticOutcome, 20, "agent_outcome")
    )
    outcome_overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    deterministic_findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    counter_argument: Mapped[str] = mapped_column(Text)
    suggested_classification: Mapped[Classification | None] = mapped_column(
        str_enum(Classification, 30, "suggested_classification")
    )
    summary: Mapped[str] = mapped_column(Text)
    ai_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_runs.id"))
    created_at: Mapped[datetime] = created_at_col()
