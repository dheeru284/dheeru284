"""Immutable document snapshots. Sources are created only by human ingest or by the
search/fetch stage; LLMs have no path to create one (no fabricated sources)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.core.hashing import sha256_text
from app.domain.enums import PRIMARY_SOURCE_TYPES, ActorType, SourceType
from app.domain.text import chunk_text
from app.models import Source, SourceChunk, User
from app.services.errors import Unprocessable
from app.services.registry import find_entry_for_url

MAX_SOURCE_CHARS = 2_000_000
MIN_SOURCE_CHARS = 20


def store_source(
    session: Session,
    *,
    title: str,
    content_text: str,
    url: str | None,
    publisher_name: str | None,
    published_at: datetime | None,
    source_type: SourceType | None,
    language: str,
    retrieval_provider: str,
    fetch_metadata: dict[str, Any] | None = None,
    ingested_by: User | None = None,
) -> tuple[Source, bool]:
    """Store a snapshot (or return the existing one with identical content).
    Returns (source, created)."""
    text = content_text.strip()
    if len(text) < MIN_SOURCE_CHARS:
        raise Unprocessable("Source content is too short to be evidence.")
    if len(text) > MAX_SOURCE_CHARS:
        raise Unprocessable(f"Source content exceeds {MAX_SOURCE_CHARS} characters.")
    digest = sha256_text(text)
    existing = session.scalar(select(Source).where(Source.content_sha256 == digest))
    if existing is not None:
        return existing, False

    entry = find_entry_for_url(session, url)
    resolved_type = source_type or (entry.default_source_type if entry else SourceType.OTHER)
    source = Source(
        registry_source_id=entry.id if entry else None,
        source_type=resolved_type,
        is_primary=bool(entry and entry.is_primary_source) or resolved_type in PRIMARY_SOURCE_TYPES,
        title=title.strip()[:1000] or "(untitled)",
        url=url,
        publisher_name=publisher_name or (entry.name if entry else None),
        published_at=published_at,
        retrieved_at=datetime.now(UTC),
        retrieval_provider=retrieval_provider,
        language=language,
        content_text=text,
        content_sha256=digest,
        fetch_metadata=fetch_metadata or {},
        ingested_by_id=ingested_by.id if ingested_by else None,
    )
    session.add(source)
    session.flush()
    for c in chunk_text(text):
        session.add(
            SourceChunk(
                source_id=source.id,
                chunk_index=c.index,
                text=c.text,
                char_start=c.start,
                char_end=c.end,
            )
        )
    session.flush()
    AuditService(session).record(
        actor_type=ActorType.USER if ingested_by else ActorType.SYSTEM,
        actor_id=str(ingested_by.id) if ingested_by else f"system:{retrieval_provider}",
        action="source.created",
        entity_type="source",
        entity_id=source.id,
        payload={
            "title": source.title,
            "url": url,
            "publisher": source.publisher_name,
            "source_type": source.source_type.value,
            "is_primary": source.is_primary,
            "registry_source_id": str(entry.id) if entry else None,
            "content_sha256": digest,
            "retrieval_provider": retrieval_provider,
        },
    )
    return source, True
