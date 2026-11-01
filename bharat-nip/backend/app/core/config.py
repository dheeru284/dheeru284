"""Application settings, loaded from ``BNIP_*`` environment variables.

Mock providers (LLM, embeddings, search) are test infrastructure. They are refused in
production always, and in development unless ``BNIP_ALLOW_MOCK_PROVIDERS=true``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
LLMProviderName = Literal["ollama", "mock"]
EmbeddingProviderName = Literal["ollama", "mock"]
SearchProviderName = Literal["local_corpus", "searxng", "mock"]
PipelineExecution = Literal["celery", "inline"]

MOCK_PROVIDERS = {"mock"}

# Fixed by the source_chunks.embedding column (vector(768)). Changing it needs a migration.
SCHEMA_EMBEDDING_DIMENSIONS = 768

# Only used outside production when BNIP_JWT_SECRET is unset. Never valid in production.
DEV_JWT_SECRET = "bnip-development-only-secret-do-not-use-in-production"

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BNIP_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    env: Environment = "development"
    app_version: str = "0.2.0"

    database_url: str = "postgresql+psycopg://bnip:bnip@localhost:5432/bnip"
    redis_url: str = "redis://localhost:6379/0"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- auth ---
    jwt_secret: str | None = None
    jwt_expiry_minutes: int = Field(default=60, ge=5, le=24 * 60)

    # --- AI providers ---
    llm_provider: LLMProviderName = "ollama"
    embedding_provider: EmbeddingProviderName = "ollama"
    allow_mock_providers: bool = False
    # JSON file with scripted mock responses (LLM + search). Non-production only.
    mock_fixtures_path: Path | None = None

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    # The critic may run on a different model for independence. Defaults to ollama_model.
    ollama_critic_model: str | None = None
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_timeout_seconds: float = 120.0

    embedding_dimensions: int = 768
    max_revision_rounds: int = Field(default=2, ge=0, le=5)

    # --- search / retrieval ---
    search_providers: list[SearchProviderName] = Field(default_factory=lambda: ["local_corpus"])
    searxng_url: str | None = None
    search_results_per_query: int = Field(default=5, ge=1, le=20)
    max_evidence_chunks: int = Field(default=8, ge=1, le=30)

    # --- fetching (URL submissions and web search results) ---
    fetch_timeout_seconds: float = 15.0
    fetch_max_bytes: int = 5_000_000
    fetch_allow_http: bool = False  # https only by default
    fetch_user_agent: str = "BNIP-FactCheck/0.2 (+evidence retrieval)"

    # --- uploads ---
    storage_dir: Path = BACKEND_ROOT / "storage"
    max_upload_bytes: int = 15_000_000

    # --- pipeline ---
    pipeline_execution: PipelineExecution = "celery"

    @property
    def uses_mock(self) -> bool:
        return (
            self.llm_provider in MOCK_PROVIDERS
            or self.embedding_provider in MOCK_PROVIDERS
            or any(p in MOCK_PROVIDERS for p in self.search_providers)
        )

    @property
    def effective_jwt_secret(self) -> str:
        return self.jwt_secret or DEV_JWT_SECRET

    @model_validator(mode="after")
    def _guard_mock_providers(self) -> Settings:
        if self.uses_mock or self.mock_fixtures_path is not None:
            if self.env == "production":
                raise ValueError("Mock providers are not allowed when BNIP_ENV=production.")
            if self.env == "development" and not self.allow_mock_providers:
                raise ValueError(
                    "Mock providers in development require BNIP_ALLOW_MOCK_PROVIDERS=true."
                )
        return self

    @model_validator(mode="after")
    def _guard_embedding_dimensions(self) -> Settings:
        if self.embedding_dimensions != SCHEMA_EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"BNIP_EMBEDDING_DIMENSIONS must be {SCHEMA_EMBEDDING_DIMENSIONS} to match the "
                "database schema (source_chunks.embedding)."
            )
        return self

    @model_validator(mode="after")
    def _guard_search(self) -> Settings:
        if not self.search_providers:
            raise ValueError("BNIP_SEARCH_PROVIDERS must list at least one provider.")
        if "searxng" in self.search_providers and not self.searxng_url:
            raise ValueError("BNIP_SEARXNG_URL is required when 'searxng' is a search provider.")
        return self

    @model_validator(mode="after")
    def _guard_production_secrets(self) -> Settings:
        if self.env == "production" and (not self.jwt_secret or len(self.jwt_secret) < 32):
            raise ValueError("BNIP_JWT_SECRET (>=32 chars) is required in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
