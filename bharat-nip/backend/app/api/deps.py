from __future__ import annotations

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.llm.base import LLMProvider
from app.providers.registry import get_embedding_provider, get_llm_provider

__all__ = [
    "get_db",
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
