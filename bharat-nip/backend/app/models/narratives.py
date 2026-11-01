"""Narrative intelligence tables (NARRATIVE_INTELLIGENCE.md, DATABASE_DESIGN.md §3.18+).

Nothing here describes individual members of the public: narratives are clusters of claims,
observations are aggregate counts per channel.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, str_enum, updated_at_col, uuid_pk
from app.domain.enums import (
    EvidenceStatus,
    HarmCategory,
    HarmSeverity,
    MembershipSource,
    NarrativeOrigin,
    NarrativeStatus,
    ObservationMetric,
    Recommendation,
    RelationType,
    ResponseType,
)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = uuid_pk()
    label: Mapped[str] = mapped_column(String(300))
    keywords: Mapped[list[str]] = mapped_column(JSONB, default=list)
    claim_count: Mapped[int] = mapped_column(Integer, default=0)
    recent_count: Mapped[int] = mapped_column(Integer, default=0)
    baseline_weekly: Mapped[float] = mapped_column(Float, default=0.0)
    is_emerging: Mapped[bool] = mapped_column(Boolean, default=False)
    emerging_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class TopicClaim(Base):
    """Derived: recomputed by every engine run."""

    __tablename__ = "topic_claims"

    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id"), primary_key=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"), index=True)


class Narrative(Base):
    __tablename__ = "narratives"
    __table_args__ = (
        CheckConstraint(
            "harm_severity IN ('UNASSESSED', 'NONE')"
            " OR (harm_rationale IS NOT NULL AND harm_rationale <> '')",
            name="harm_rationale_required",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[NarrativeStatus] = mapped_column(
        str_enum(NarrativeStatus, 20, "status"), default=NarrativeStatus.EMERGING, index=True
    )
    origin: Mapped[NarrativeOrigin] = mapped_column(str_enum(NarrativeOrigin, 20, "origin"))
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Potential harm: assessed by an analyst, never inferred from who a narrative helps.
    harm_category: Mapped[HarmCategory] = mapped_column(
        str_enum(HarmCategory, 30, "harm_category"), default=HarmCategory.NONE
    )
    harm_severity: Mapped[HarmSeverity] = mapped_column(
        str_enum(HarmSeverity, 20, "harm_severity"), default=HarmSeverity.UNASSESSED
    )
    harm_rationale: Mapped[str | None] = mapped_column(Text)
    harm_assessed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    harm_assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_note: Mapped[str | None] = mapped_column(Text)
    status_changed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class NarrativeClaim(Base):
    __tablename__ = "narrative_claims"
    __table_args__ = (UniqueConstraint("claim_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    narrative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("narratives.id"), index=True)
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id"))
    similarity: Mapped[float | None] = mapped_column(Float)
    added_by: Mapped[MembershipSource] = mapped_column(str_enum(MembershipSource, 10, "added_by"))
    added_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # An analyst removed this claim from the narrative. The row stays so the engine never
    # silently re-adds it; the claim is not clustered elsewhere unless an analyst moves it.
    excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_at_col()


class NarrativeRelation(Base):
    """Derived, undirected (source_id < target_id); recomputed by every engine run."""

    __tablename__ = "narrative_relations"
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "relation_type"),
        CheckConstraint("source_id < target_id", name="ordered_pair"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("narratives.id"), index=True)
    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("narratives.id"), index=True)
    relation_type: Mapped[RelationType] = mapped_column(str_enum(RelationType, 20, "relation_type"))
    weight: Mapped[float] = mapped_column(Float)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = created_at_col()


class NarrativeMetric(Base):
    """A metrics + recommendation snapshot. Written when something changed."""

    __tablename__ = "narrative_metrics"
    __table_args__ = (
        CheckConstraint(
            "evidence_strength BETWEEN 0 AND 1 AND public_interest BETWEEN 0 AND 1"
            " AND momentum BETWEEN 0 AND 1 AND uncertainty BETWEEN 0 AND 1"
            " AND coverage BETWEEN 0 AND 1",
            name="unit_ranges",
        ),
        UniqueConstraint("narrative_id", "version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    narrative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("narratives.id"), index=True)
    # Monotonic per narrative: the latest snapshot is the highest version.
    version: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    engine_version: Mapped[str] = mapped_column(String(20))
    claim_count: Mapped[int] = mapped_column(Integer)
    rate_7d: Mapped[float] = mapped_column(Float)
    acceleration: Mapped[int] = mapped_column(Integer)
    recurring: Mapped[bool] = mapped_column(Boolean)
    evidence_status: Mapped[EvidenceStatus] = mapped_column(
        str_enum(EvidenceStatus, 30, "evidence_status")
    )
    evidence_strength: Mapped[float] = mapped_column(Float)
    public_interest: Mapped[float] = mapped_column(Float)
    momentum: Mapped[float] = mapped_column(Float)
    harm_score: Mapped[float | None] = mapped_column(Float)
    uncertainty: Mapped[float] = mapped_column(Float)
    coverage: Mapped[float] = mapped_column(Float)
    recommendation: Mapped[Recommendation] = mapped_column(
        str_enum(Recommendation, 20, "recommendation")
    )
    suggested_status: Mapped[NarrativeStatus] = mapped_column(
        str_enum(NarrativeStatus, 20, "suggested_status")
    )
    # Full inputs, indicator breakdowns, harm signals and the rule trace.
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_col()


class NarrativeObservation(Base):
    """An aggregate public count (no individual, account or handle fields by design)."""

    __tablename__ = "narrative_observations"
    __table_args__ = (CheckConstraint("value >= 0", name="value_nonnegative"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    narrative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("narratives.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    channel: Mapped[str] = mapped_column(String(100))
    metric: Mapped[ObservationMetric] = mapped_column(str_enum(ObservationMetric, 20, "metric"))
    value: Mapped[int] = mapped_column(BigInteger)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    note: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()


class NarrativeResponse(Base):
    """Existing response coverage: what has already been said about this narrative."""

    __tablename__ = "narrative_responses"

    id: Mapped[uuid.UUID] = uuid_pk()
    narrative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("narratives.id"), index=True)
    response_type: Mapped[ResponseType] = mapped_column(str_enum(ResponseType, 30, "response_type"))
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(2048))
    channel: Mapped[str | None] = mapped_column(String(100))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()
