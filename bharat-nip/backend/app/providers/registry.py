"""Builds providers from settings. New providers (OpenAI, Anthropic, Gemini, ...) are
registered here when implemented; nothing else in the app needs to change."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.embeddings.mock import MockEmbeddingProvider
from app.providers.embeddings.ollama import OllamaEmbeddingProvider
from app.providers.llm.base import LLMProvider
from app.providers.llm.mock import MockLLMProvider
from app.providers.llm.ollama import OllamaLLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    match settings.llm_provider:
        case "ollama":
            return OllamaLLMProvider(
                settings.ollama_base_url, settings.ollama_model, settings.ollama_timeout_seconds
            )
        case "mock":
            return MockLLMProvider()
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    match settings.embedding_provider:
        case "ollama":
            return OllamaEmbeddingProvider(
                settings.ollama_base_url,
                settings.ollama_embedding_model,
                settings.embedding_dimensions,
                settings.ollama_timeout_seconds,
            )
        case "mock":
            return MockEmbeddingProvider(settings.embedding_dimensions)
    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")


@lru_cache
def get_llm_provider() -> LLMProvider:
    return build_llm_provider(get_settings())


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return build_embedding_provider(get_settings())
