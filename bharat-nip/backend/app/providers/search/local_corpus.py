"""Searches documents analysts have ingested (POST /sources) with PostgreSQL full-text
search. Free, offline and fully traceable: every hit is an existing stored source."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Source, SourceChunk
from app.providers.base import ProviderHealth
from app.providers.search.base import SearchHit

# Queries are matched with OR semantics over meaningful words so that paraphrased claims
# still find relevant documents; ranking (ts_rank) puts the best matches first.
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "will",
        "with",
        "said",
        "says",
        "speaker",
        "organization",
    ]
)


def _or_query(query: str) -> str:
    words = [
        "".join(ch for ch in w if ch.isalnum())
        for w in query.lower().replace("[", " ").replace("]", " ").split()
    ]
    terms = sorted({w for w in words if len(w) > 2 and w not in _STOPWORDS})
    return " | ".join(terms)


class LocalCorpusSearchProvider:
    name = "local_corpus"
    is_mock = False

    def search(self, query: str, limit: int, *, session: Session) -> list[SearchHit]:
        expr = _or_query(query)
        if not expr:
            return []
        tsq = func.to_tsquery("simple", expr)
        rank = func.max(func.ts_rank(SourceChunk.text_search, tsq)).label("rank")
        rows = session.execute(
            select(Source, rank)
            .join(SourceChunk, SourceChunk.source_id == Source.id)
            .where(SourceChunk.text_search.op("@@")(tsq))
            .group_by(Source.id)
            .order_by(rank.desc(), Source.id)
            .limit(limit)
        ).all()
        return [
            SearchHit(
                title=src.title,
                url=src.url,
                publisher=src.publisher_name,
                published_at=src.published_at,
                content=src.content_text,
                source_type=src.source_type,
                score=float(r),
                source_id=src.id,
            )
            for src, r in rows
        ]

    def health(self) -> ProviderHealth:
        return ProviderHealth(ok=True, detail="Local corpus (PostgreSQL full-text search)")
