"""Ollama chat provider (https://github.com/ollama/ollama/blob/main/docs/api.md)."""

from __future__ import annotations

import time

import httpx

from app.providers.base import ProviderError, ProviderHealth
from app.providers.llm.base import LLMRequest, LLMResponse, TokenUsage


class OllamaLLMProvider:
    name = "ollama"
    is_mock = False

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds, transport=transport
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        options: dict[str, object] = {
            "temperature": request.temperature,
            "num_predict": request.max_tokens,
        }
        if request.seed is not None:
            options["seed"] = request.seed
        body: dict[str, object] = {
            "model": self.model,
            "messages": [m.model_dump() for m in request.messages],
            "stream": False,
            "options": options,
        }
        if request.response_schema is not None:
            body["format"] = request.response_schema

        started = time.monotonic()
        try:
            resp = self._client.post("/api/chat", json=body)
            resp.raise_for_status()
            data = resp.json()
            text = data["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            raise ProviderError(f"Ollama chat failed: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)
        return LLMResponse(
            text=text,
            provider=self.name,
            model=data.get("model", self.model),
            usage=TokenUsage(
                prompt_tokens=data.get("prompt_eval_count"),
                completion_tokens=data.get("eval_count"),
            ),
            latency_ms=latency_ms,
        )

    def health(self) -> ProviderHealth:
        try:
            resp = self._client.get("/api/tags", timeout=3.0)
            resp.raise_for_status()
            names = {m.get("name", "") for m in resp.json().get("models", [])}
        except (httpx.HTTPError, ValueError) as exc:
            return ProviderHealth(ok=False, detail=f"Ollama unreachable: {exc}")
        if not _model_available(self.model, names):
            return ProviderHealth(
                ok=False, detail=f"Ollama reachable but model '{self.model}' is not pulled"
            )
        return ProviderHealth(ok=True, detail=f"Ollama reachable; model '{self.model}' available")


def _model_available(model: str, names: set[str]) -> bool:
    # Ollama reports "name:tag"; an untagged model name means ":latest".
    wanted = model if ":" in model else f"{model}:latest"
    return wanted in names or model in names
