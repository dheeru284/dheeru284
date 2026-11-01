"""SearchProvider protocol (AI_AGENT_ARCHITECTURE.md §5).

A search provider finds candidate documents for a query. It never fabricates sources:
results are either (a) URLs that the pipeline then fetches and snapshots, or
(b) documents the provider already holds verbatim (local corpus, scripted mock).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.domain.enums import SourceType
from app.providers.base import ProviderHealth


class SearchHit(BaseModel):
    title: str
    url: str | None = None
    snippet: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    # Full document text when the provider holds it; otherwise the pipeline fetches `url`.
    content: str | None = None
    source_type: SourceType | None = None
    score: float | None = None
    # Set when the hit is an already-stored source (local corpus).
    source_id: uuid.UUID | None = None


@runtime_checkable
class SearchProvider(Protocol):
    name: str
    is_mock: bool

    def search(self, query: str, limit: int, *, session: Session) -> list[SearchHit]: ...

    def health(self) -> ProviderHealth: ...


class SearchError(Exception):
    pass
