"""Records every LLM call in ``ai_runs`` (principle: every AI output records
model/provider/prompt version). Agents must go through this; see
AI_AGENT_ARCHITECTURE.md §6."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.ai.prompts import PromptTemplate
from app.audit.service import AuditService
from app.core.hashing import sha256_json
from app.domain.enums import ActorType, AIRunStatus
from app.models.ai import AIRun
from app.providers.llm.base import LLMProvider, LLMRequest, LLMResponse


class AIRunRecorder:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        agent_name: str,
        agent_version: str,
        prompt: PromptTemplate,
        provider: LLMProvider,
        request: LLMRequest,
        response: LLMResponse | None,
        status: AIRunStatus,
        output_parsed: dict[str, Any] | None = None,
        error: str | None = None,
        attempt: int = 1,
        pipeline_job_id: uuid.UUID | None = None,
    ) -> AIRun:
        if request.prompt_id != prompt.prompt_id:
            raise ValueError("request.prompt_id does not match the prompt template")
        if status is AIRunStatus.SUCCEEDED and response is None:
            raise ValueError("A SUCCEEDED run must have a response")
        messages = [m.model_dump() for m in request.messages]
        run = AIRun(
            agent_name=agent_name,
            agent_version=agent_version,
            # Prefer what the provider reports; fall back to its configured identity.
            provider=response.provider if response else provider.name,
            model=response.model if response else provider.model,
            prompt_id=prompt.prompt_id,
            prompt_version=prompt.version,
            prompt_sha256=prompt.sha256,
            input_sha256=sha256_json(messages),
            input_messages=messages,
            parameters=request.parameters(),
            output_text=response.text if response else None,
            output_parsed=output_parsed,
            status=status,
            error=error,
            prompt_tokens=response.usage.prompt_tokens if response else None,
            completion_tokens=response.usage.completion_tokens if response else None,
            latency_ms=response.latency_ms if response else None,
            attempt=attempt,
            pipeline_job_id=pipeline_job_id,
        )
        self.session.add(run)
        self.session.flush()
        AuditService(self.session).record(
            actor_type=ActorType.AGENT,
            actor_id=agent_name,
            action="ai_run.recorded",
            entity_type="ai_run",
            entity_id=run.id,
            payload={
                "agent_version": agent_version,
                "provider": run.provider,
                "model": run.model,
                "prompt_id": run.prompt_id,
                "prompt_version": run.prompt_version,
                "prompt_sha256": run.prompt_sha256,
                "status": run.status.value,
                "attempt": attempt,
                "error": error,
            },
        )
        return run
