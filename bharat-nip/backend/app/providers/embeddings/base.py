from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from app.providers.base import ProviderHealth


class EmbeddingResult(BaseModel):
    vectors: list[list[float]]
    provider: str
    model: str


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    model: str
    dimensions: int
    is_mock: bool

    def embed(self, texts: list[str]) -> EmbeddingResult: ...

    def health(self) -> ProviderHealth: ...
