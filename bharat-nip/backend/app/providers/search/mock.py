"""Scripted mock search provider. TEST INFRASTRUCTURE ONLY.

Returns only explicitly scripted hits. An unscripted query raises
``MockSearchNotScripted`` so a test can never pass on silently-empty search.
Script an empty list to simulate "nothing found".
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.providers.base import ProviderHealth
from app.providers.search.base import SearchHit


class MockSearchNotScripted(Exception):
    pass


@dataclass
class _Rule:
    when_contains: str | None
    hits: list[SearchHit]


class MockSearchProvider:
    name = "mock"
    is_mock = True

    def __init__(self) -> None:
        self._rules: list[_Rule] = []
        self.queries: list[str] = []

    def script(self, hits: list[SearchHit], when_contains: str | None = None) -> None:
        """Return ``hits`` for queries containing ``when_contains`` (case-insensitive),
        or for any query when it is None. First matching rule wins."""
        self._rules.append(_Rule(when_contains.lower() if when_contains else None, hits))

    def search(self, query: str, limit: int, *, session: Session) -> list[SearchHit]:
        self.queries.append(query)
        q = query.lower()
        for rule in self._rules:
            if rule.when_contains is None or rule.when_contains in q:
                return [h.model_copy() for h in rule.hits[:limit]]
        raise MockSearchNotScripted(f"No scripted mock search results for query {query!r}")

    def health(self) -> ProviderHealth:
        return ProviderHealth(ok=True, detail="Mock search provider (scripted test results only)")
