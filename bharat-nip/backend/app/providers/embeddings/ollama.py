from __future__ import annotations

import httpx

from app.providers.base import ProviderError, ProviderHealth
from app.providers.embeddings.base import EmbeddingResult
from app.providers.llm.ollama import _model_available


class OllamaEmbeddingProvider:
    name = "ollama"
    is_mock = False

    def __init__(
        self,
        base_url: str,
        model: str,
        dimensions: int,
        timeout_seconds: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self.dimensions = dimensions
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds, transport=transport
        )

    def embed(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(vectors=[], provider=self.name, model=self.model)
        try:
            resp = self._client.post("/api/embed", json={"model": self.model, "input": texts})
            resp.raise_for_status()
            vectors = resp.json()["embeddings"]
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            raise ProviderError(f"Ollama embed failed: {exc}") from exc
        if len(vectors) != len(texts) or any(len(v) != self.dimensions for v in vectors):
            raise ProviderError(
                f"Ollama returned embeddings with unexpected shape (expected "
                f"{len(texts)} x {self.dimensions})"
            )
        return EmbeddingResult(vectors=vectors, provider=self.name, model=self.model)

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
