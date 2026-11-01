from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, str_enum, updated_at_col, uuid_pk
from app.domain.enums import AIRunStatus, PipelineJobStatus, PipelineStage


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"
    __table_args__ = (
        CheckConstraint("submission_id IS NOT NULL OR claim_id IS NOT NULL", name="target"),
        CheckConstraint("attempt >= 1 AND attempt <= max_attempts", name="attempt_bound"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    submission_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("submissions.id"))
    claim_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("claims.id"), index=True)
    stage: Mapped[PipelineStage] = mapped_column(str_enum(PipelineStage, 30, "stage"))
    status: Mapped[PipelineJobStatus] = mapped_column(
        str_enum(PipelineJobStatus, 20, "status"), default=PipelineJobStatus.QUEUED
    )
    attempt: Mapped[int] = mapped_column(Integer, server_default="1", default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, server_default="3", default=3)
    celery_task_id: Mapped[str | None] = mapped_column(String(255))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class AIRun(Base):
    """One row per LLM call, including failed and invalid ones (AI_AGENT_ARCHITECTURE.md §6)."""

    __tablename__ = "ai_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    agent_name: Mapped[str] = mapped_column(String(100), index=True)
    agent_version: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(200))
    prompt_id: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(20))
    prompt_sha256: Mapped[str] = mapped_column(String(64))
    input_sha256: Mapped[str] = mapped_column(String(64))
    input_messages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB)
    output_text: Mapped[str | None] = mapped_column(Text)
    output_parsed: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[AIRunStatus] = mapped_column(str_enum(AIRunStatus, 20, "status"))
    error: Mapped[str | None] = mapped_column(Text)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    attempt: Mapped[int] = mapped_column(Integer, server_default="1", default=1)
    # use_alter breaks the claims -> ai_runs -> pipeline_jobs -> claims FK cycle.
    pipeline_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_jobs.id", use_alter=True)
    )
    created_at: Mapped[datetime] = created_at_col()
