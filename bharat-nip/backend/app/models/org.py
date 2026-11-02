"""Agent organization tables (AGENT_ORGANIZATION.md). Agent definitions live in code
(app/org/agents.py); these tables hold tasks, steps, the execution log and approvals."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, str_enum, updated_at_col, uuid_pk
from app.domain.enums import (
    ApprovalDecision,
    ApprovalLevel,
    ApproverType,
    ExecutionKind,
    ExecutionStatus,
    OrgTaskStatus,
    ReviewerType,
    StepStatus,
    WorkflowType,
)


class OrgTask(Base):
    __tablename__ = "org_tasks"

    id: Mapped[uuid.UUID] = uuid_pk()
    workflow: Mapped[WorkflowType] = mapped_column(str_enum(WorkflowType, 40, "workflow"))
    title: Mapped[str] = mapped_column(String(500))
    input: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[OrgTaskStatus] = mapped_column(
        str_enum(OrgTaskStatus, 30, "status"), default=OrgTaskStatus.PENDING, index=True
    )
    approval_level: Mapped[ApprovalLevel] = mapped_column(
        str_enum(ApprovalLevel, 20, "approval_level")
    )
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    escalation_reason: Mapped[str | None] = mapped_column(Text)
    executions_used: Mapped[int] = mapped_column(Integer, default=0)
    human_revisions: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class OrgTaskStep(Base):
    __tablename__ = "org_task_steps"
    __table_args__ = (
        UniqueConstraint("task_id", "step_key"),
        CheckConstraint("iterations >= 0", name="iterations_nonnegative"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_tasks.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    step_key: Mapped[str] = mapped_column(String(60))
    agent_key: Mapped[str] = mapped_column(String(60), index=True)
    delegated_by: Mapped[str] = mapped_column(String(60))
    depends_on: Mapped[list[str]] = mapped_column(JSONB, default=list)
    reviewer: Mapped[ReviewerType] = mapped_column(str_enum(ReviewerType, 20, "reviewer"))
    status: Mapped[StepStatus] = mapped_column(
        str_enum(StepStatus, 20, "status"), default=StepStatus.PENDING
    )
    iterations: Mapped[int] = mapped_column(Integer, default=0)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    feedback: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    escalation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class OrgExecution(Base):
    """The execution log: every delegation, execution, review, revision, escalation,
    approval and completion."""

    __tablename__ = "org_executions"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Total order of the log (created_at is the same for every row in one transaction).
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_tasks.id"), index=True)
    step_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("org_task_steps.id"))
    agent_key: Mapped[str] = mapped_column(String(60), index=True)
    kind: Mapped[ExecutionKind] = mapped_column(str_enum(ExecutionKind, 20, "kind"))
    status: Mapped[ExecutionStatus] = mapped_column(str_enum(ExecutionStatus, 20, "status"))
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_runs.id"))
    model: Mapped[str | None] = mapped_column(String(200))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()


class OrgApproval(Base):
    __tablename__ = "org_approvals"
    __table_args__ = (
        CheckConstraint(
            "(approver_type = 'HUMAN' AND approver_user_id IS NOT NULL)"
            " OR (approver_type = 'AGENT' AND approver_agent IS NOT NULL)",
            name="approver_identity",
        ),
        CheckConstraint(
            "decision = 'APPROVED' OR (notes IS NOT NULL AND notes <> '')", name="notes_required"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_tasks.id"), index=True)
    approver_type: Mapped[ApproverType] = mapped_column(str_enum(ApproverType, 10, "approver_type"))
    approver_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approver_agent: Mapped[str | None] = mapped_column(String(60))
    decision: Mapped[ApprovalDecision] = mapped_column(str_enum(ApprovalDecision, 30, "decision"))
    target_step: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
