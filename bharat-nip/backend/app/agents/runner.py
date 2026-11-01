"""The agent call contract (AI_AGENT_ARCHITECTURE.md §6).

render prompt -> call provider -> parse JSON -> validate schema -> semantic validation
-> record ai_run (every attempt) -> retry invalid output with the error appended,
bounded by ``max_attempts`` -> return validated output or raise AgentFailed.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.ai.prompts import PromptRegistry, PromptTemplate
from app.ai.runs import AIRunRecorder
from app.domain.enums import AIRunStatus
from app.models import AIRun
from app.providers.base import ProviderError
from app.providers.llm.base import ChatMessage, LLMProvider, LLMRequest
from app.providers.llm.mock import MockResponseNotScripted

T = TypeVar("T", bound=BaseModel)


class AgentFailed(Exception):
    def __init__(self, agent: str, detail: str, last_run_id: uuid.UUID | None = None) -> None:
        super().__init__(f"{agent}: {detail}")
        self.agent = agent
        self.detail = detail
        self.last_run_id = last_run_id


class InvalidAgentOutput(ValueError):
    """Raised by semantic validators; triggers a bounded retry."""


@dataclass(frozen=True)
class AgentSpec[T: BaseModel]:
    name: str
    version: str
    prompt_id: str
    prompt_version: str
    output_model: type[T]
    max_tokens: int = 2048


@dataclass(frozen=True)
class AgentResult[T: BaseModel]:
    output: T
    ai_run: AIRun


@lru_cache
def default_prompt_registry() -> PromptRegistry:
    return PromptRegistry()


def _parse_json(text: str) -> object:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned)


def run_agent[T: BaseModel](
    session: Session,
    provider: LLMProvider,
    spec: AgentSpec[T],
    variables: dict[str, str],
    *,
    validate: Callable[[T], None] | None = None,
    pipeline_job_id: uuid.UUID | None = None,
    max_attempts: int = 2,
    registry: PromptRegistry | None = None,
) -> AgentResult[T]:
    prompt: PromptTemplate = (registry or default_prompt_registry()).get(
        spec.prompt_id, spec.prompt_version
    )
    system, user = prompt.render_messages(**variables)
    messages = [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]
    recorder = AIRunRecorder(session)
    last_run: AIRun | None = None

    for attempt in range(1, max_attempts + 1):
        request = LLMRequest(
            prompt_id=spec.prompt_id,
            messages=messages,
            max_tokens=spec.max_tokens,
            response_schema=spec.output_model.model_json_schema(),
        )
        common = {
            "agent_name": spec.name,
            "agent_version": spec.version,
            "prompt": prompt,
            "provider": provider,
            "request": request,
            "attempt": attempt,
            "pipeline_job_id": pipeline_job_id,
        }
        try:
            response = provider.complete(request)
        except (ProviderError, MockResponseNotScripted) as exc:
            last_run = recorder.record(
                **common, response=None, status=AIRunStatus.FAILED, error=str(exc)
            )
            raise AgentFailed(spec.name, f"provider call failed: {exc}", last_run.id) from exc

        try:
            output = spec.output_model.model_validate(_parse_json(response.text))
            if validate is not None:
                validate(output)
        except (json.JSONDecodeError, ValidationError, InvalidAgentOutput) as exc:
            error = f"{type(exc).__name__}: {exc}"
            last_run = recorder.record(
                **common, response=response, status=AIRunStatus.INVALID_OUTPUT, error=error[:4000]
            )
            messages = [
                *messages,
                ChatMessage(role="assistant", content=response.text),
                ChatMessage(
                    role="user",
                    content=(
                        "Your previous output was invalid:\n"
                        f"{error[:2000]}\n"
                        "Return only a corrected JSON object that follows every rule."
                    ),
                ),
            ]
            continue

        run = recorder.record(
            **common,
            response=response,
            status=AIRunStatus.SUCCEEDED,
            output_parsed=output.model_dump(mode="json"),
        )
        return AgentResult(output=output, ai_run=run)

    raise AgentFailed(
        spec.name,
        f"no valid output after {max_attempts} attempts",
        last_run.id if last_run else None,
    )
