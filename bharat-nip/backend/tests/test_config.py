import pytest
from pydantic import ValidationError

from app.core.config import Settings


def make(**kw) -> Settings:
    # The test session sets mock providers via env; default to real ones unless overridden.
    kw.setdefault("llm_provider", "ollama")
    kw.setdefault("embedding_provider", "ollama")
    return Settings(_env_file=None, **kw)


def test_mock_providers_refused_in_production():
    with pytest.raises(ValidationError, match="not allowed"):
        make(env="production", llm_provider="mock", jwt_secret="x" * 32)


def test_mock_providers_refused_in_production_even_with_flag():
    with pytest.raises(ValidationError, match="not allowed"):
        make(
            env="production",
            embedding_provider="mock",
            allow_mock_providers=True,
            jwt_secret="x" * 32,
        )


def test_mock_providers_in_development_need_explicit_flag():
    with pytest.raises(ValidationError, match="ALLOW_MOCK_PROVIDERS"):
        make(env="development", llm_provider="mock")
    assert make(env="development", llm_provider="mock", allow_mock_providers=True)


def test_mock_providers_allowed_in_test():
    s = make(env="test", llm_provider="mock", embedding_provider="mock")
    assert s.llm_provider == "mock"


def test_production_requires_strong_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        make(env="production")
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        make(env="production", jwt_secret="short")
    assert make(env="production", jwt_secret="x" * 32)


def test_embedding_dimensions_must_match_schema():
    with pytest.raises(ValidationError, match="768"):
        make(embedding_dimensions=1024)


def test_revision_rounds_bounded():
    with pytest.raises(ValidationError):
        make(max_revision_rounds=50)
