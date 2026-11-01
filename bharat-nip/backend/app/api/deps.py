from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.llm.base import LLMProvider
from app.providers.registry import get_embedding_provider, get_llm_provider

__all__ = [
    "get_db",
    "get_dispatcher",
    "get_embedding_provider_dep",
    "get_llm_provider_dep",
    "get_settings_dep",
]


def get_settings_dep() -> Settings:
    return get_settings()


def get_llm_provider_dep() -> LLMProvider:
    return get_llm_provider()


def get_embedding_provider_dep() -> EmbeddingProvider:
    return get_embedding_provider()


def get_dispatcher(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
):
    from app.pipeline.dispatch import CeleryDispatcher, InlineDispatcher, build_context

    if settings.pipeline_execution == "inline":
        return InlineDispatcher(build_context(db, settings))
    return CeleryDispatcher()
