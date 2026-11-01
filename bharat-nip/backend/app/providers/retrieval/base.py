"""Source retrieval protocol. The LocalCorpusProvider implementation arrives in Phase 1b.

A retrieval provider can only return chunks of sources that already exist in the
database (ingested by a human or fetched and snapshotted by a provider). It can
never return a source that has no stored snapshot.
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.domain.enums import RetrievalMethod


class RetrievedChunk(BaseModel):
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    score: float
    rank: int
    method: RetrievalMethod


@runtime_checkable
class SourceRetrievalProvider(Protocol):
    name: str

    def retrieve(self, session: Session, query_text: str, limit: int) -> list[RetrievedChunk]: ...
