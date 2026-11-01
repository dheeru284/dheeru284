"""Deterministic hash-based embeddings. TEST INFRASTRUCTURE ONLY.

Vectors are stable for identical text and unit-normalised, which is enough to
test storage and plumbing. They carry NO semantic meaning: similar texts do not
get similar vectors. Never use these for real retrieval.
"""

from __future__ import annotations

import hashlib
import math

from app.providers.base import ProviderHealth
from app.providers.embeddings.base import EmbeddingResult


class MockEmbeddingProvider:
    name = "mock"
    is_mock = True

    def __init__(self, dimensions: int = 768, model: str = "mock-hash-v1") -> None:
        self.dimensions = dimensions
        self.model = model

    def _vector(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.dimensions:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            values.extend((b / 127.5) - 1.0 for b in digest)
            counter += 1
        values = values[: self.dimensions]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    def embed(self, texts: list[str]) -> EmbeddingResult:
        return EmbeddingResult(
            vectors=[self._vector(t) for t in texts], provider=self.name, model=self.model
        )

    def health(self) -> ProviderHealth:
        return ProviderHealth(ok=True, detail="Mock embedding provider (non-semantic hash vectors)")
