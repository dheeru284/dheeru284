"""LLM provider protocol (AI_AGENT_ARCHITECTURE.md §5)."""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.providers.base import ProviderHealth


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMRequest(BaseModel):
    messages: list[ChatMessage]
    # Identifies the prompt being run. Providers may use it (the mock does); real ones ignore it.
    prompt_id: str
    temperature: float = 0.0
    max_tokens: int = 2048
    seed: int | None = 7
    # Optional JSON schema to constrain output (Ollama `format`).
    response_schema: dict[str, Any] | None = None

    def parameters(self) -> dict[str, Any]:
        """Generation parameters to record in ai_runs."""
        return {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "seed": self.seed,
            "structured_output": self.response_schema is not None,
        }


class TokenUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class LLMResponse(BaseModel):
    text: str
    provider: str
    model: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: int


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str
    is_mock: bool

    def complete(self, request: LLMRequest) -> LLMResponse: ...

    def health(self) -> ProviderHealth: ...
