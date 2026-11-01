"""Web search through a SearXNG instance (https://docs.searxng.org), an open-source,
self-hostable metasearch engine. Configure with BNIP_SEARXNG_URL. The instance must have
the JSON output format enabled (``search.formats: [html, json]`` in settings.yml).

Results are URLs plus snippets; the pipeline fetches and snapshots each page itself.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.providers.base import ProviderHealth
from app.providers.search.base import SearchError, SearchHit


def _parse_date(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


class SearxngSearchProvider:
    name = "searxng"
    is_mock = False

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 15.0,
        language: str = "en",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.language = language
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds, transport=transport
        )

    def search(self, query: str, limit: int, *, session: Session) -> list[SearchHit]:
        try:
            resp = self._client.get(
                "/search",
                params={"q": query, "format": "json", "language": self.language},
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except (httpx.HTTPError, ValueError) as exc:
            raise SearchError(f"SearXNG search failed: {exc}") from exc
        hits: list[SearchHit] = []
        for item in results:
            url = item.get("url")
            title = (item.get("title") or "").strip()
            if not url or not title:
                continue
            hits.append(
                SearchHit(
                    title=title[:1000],
                    url=url,
                    snippet=item.get("content"),
                    published_at=_parse_date(item.get("publishedDate")),
                    score=item.get("score"),
                )
            )
            if len(hits) >= limit:
                break
        return hits

    def health(self) -> ProviderHealth:
        try:
            resp = self._client.get("/healthz", timeout=3.0)
            ok = resp.status_code == 200
        except httpx.HTTPError as exc:
            return ProviderHealth(ok=False, detail=f"SearXNG unreachable: {exc}")
        return ProviderHealth(
            ok=ok, detail="SearXNG reachable" if ok else f"HTTP {resp.status_code}"
        )
