"""Application settings, loaded from ``BNIP_*`` environment variables.

Mock providers are test infrastructure. They are refused in production
always, and in development unless ``BNIP_ALLOW_MOCK_PROVIDERS=true``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
LLMProviderName = Literal["ollama", "mock"]
EmbeddingProviderName = Literal["ollama", "mock"]

MOCK_PROVIDERS = {"mock"}

# Fixed by the source_chunks.embedding column (vector(768)). Changing it needs a migration.
SCHEMA_EMBEDDING_DIMENSIONS = 768


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BNIP_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    env: Environment = "development"
    app_version: str = "0.1.0"

    database_url: str = "postgresql+psycopg://bnip:bnip@localhost:5432/bnip"
    redis_url: str = "redis://localhost:6379/0"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    jwt_secret: str | None = None

    llm_provider: LLMProviderName = "ollama"
    embedding_provider: EmbeddingProviderName = "ollama"
    allow_mock_providers: bool = False

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_timeout_seconds: float = 120.0

    embedding_dimensions: int = 768
    max_revision_rounds: int = Field(default=2, ge=0, le=5)

    @model_validator(mode="after")
    def _guard_mock_providers(self) -> Settings:
        uses_mock = self.llm_provider in MOCK_PROVIDERS or self.embedding_provider in MOCK_PROVIDERS
        if uses_mock:
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
    def _guard_production_secrets(self) -> Settings:
        if self.env == "production" and (not self.jwt_secret or len(self.jwt_secret) < 32):
            raise ValueError("BNIP_JWT_SECRET (>=32 chars) is required in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
