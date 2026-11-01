"""Builds providers from settings. New providers (OpenAI, Anthropic, Gemini, Brave, ...)
are registered here when implemented; nothing else in the app needs to change."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.embeddings.mock import MockEmbeddingProvider
from app.providers.embeddings.ollama import OllamaEmbeddingProvider
from app.providers.fixtures import load_fixtures
from app.providers.llm.base import LLMProvider
from app.providers.llm.mock import MockLLMProvider
from app.providers.llm.ollama import OllamaLLMProvider
from app.providers.search.base import SearchProvider
from app.providers.search.local_corpus import LocalCorpusSearchProvider
from app.providers.search.mock import MockSearchProvider
from app.providers.search.searxng import SearxngSearchProvider


def build_llm_provider(settings: Settings, *, model: str | None = None) -> LLMProvider:
    match settings.llm_provider:
        case "ollama":
            return OllamaLLMProvider(
                settings.ollama_base_url,
                model or settings.ollama_model,
                settings.ollama_timeout_seconds,
            )
        case "mock":
            provider = MockLLMProvider()
            if settings.mock_fixtures_path:
                load_fixtures(settings.mock_fixtures_path, provider, None)
            return provider
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


def build_search_providers(settings: Settings) -> list[SearchProvider]:
    providers: list[SearchProvider] = []
    for name in settings.search_providers:
        match name:
            case "local_corpus":
                providers.append(LocalCorpusSearchProvider())
            case "searxng":
                assert settings.searxng_url  # enforced by Settings
                providers.append(
                    SearxngSearchProvider(settings.searxng_url, settings.fetch_timeout_seconds)
                )
            case "mock":
                mock = MockSearchProvider()
                if settings.mock_fixtures_path:
                    load_fixtures(settings.mock_fixtures_path, None, mock)
                providers.append(mock)
    return providers


@lru_cache
def get_llm_provider() -> LLMProvider:
    return build_llm_provider(get_settings())


@lru_cache
def get_critic_llm_provider() -> LLMProvider:
    """The critic may use a different model for independence (BNIP_OLLAMA_CRITIC_MODEL)."""
    settings = get_settings()
    if settings.llm_provider == "ollama" and settings.ollama_critic_model:
        return build_llm_provider(settings, model=settings.ollama_critic_model)
    return get_llm_provider()


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return build_embedding_provider(get_settings())


@lru_cache
def get_search_providers() -> tuple[SearchProvider, ...]:
    return tuple(build_search_providers(get_settings()))
