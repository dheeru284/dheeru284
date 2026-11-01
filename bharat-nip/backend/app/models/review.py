from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, str_enum, updated_at_col, uuid_pk
from app.domain.enums import Classification, ReviewDecisionType, ReviewReason, ReviewTaskStatus


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: Mapped[uuid.UUID] = uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id"), index=True)
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assessments.id"))
    reason: Mapped[ReviewReason] = mapped_column(str_enum(ReviewReason, 30, "reason"))
    reason_detail: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer)
    status: Mapped[ReviewTaskStatus] = mapped_column(
        str_enum(ReviewTaskStatus, 20, "status"), default=ReviewTaskStatus.OPEN, index=True
    )
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class ReviewDecision(Base):
    """Only humans write these. Reviewer must not be the submitter (service-enforced)."""

    __tablename__ = "review_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision <> 'APPROVE' OR final_classification IS NOT NULL",
            name="final_classification_required",
        ),
        CheckConstraint(
            "decision = 'APPROVE' OR (notes IS NOT NULL AND notes <> '')",
            name="notes_required",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    review_task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("review_tasks.id"), unique=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[ReviewDecisionType] = mapped_column(
        str_enum(ReviewDecisionType, 30, "decision")
    )
    final_classification: Mapped[Classification | None] = mapped_column(
        str_enum(Classification, 30, "final_classification")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
