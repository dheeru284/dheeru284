"""Test fixtures. DB tests run against a real PostgreSQL + pgvector database
(TESTING_STRATEGY.md §2): the schema is rebuilt from migrations once per session
and every test runs inside a transaction that is rolled back."""

from __future__ import annotations

import os

# Must be set before any app module reads settings.
TEST_DATABASE_URL = os.environ.get(
    "BNIP_TEST_DATABASE_URL", "postgresql+psycopg://bnip:bnip@localhost:5432/bnip_test"
)
os.environ["BNIP_ENV"] = "test"
os.environ["BNIP_DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BNIP_LLM_PROVIDER"] = "mock"
os.environ["BNIP_EMBEDDING_PROVIDER"] = "mock"

from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.api import deps  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.providers.embeddings.mock import MockEmbeddingProvider  # noqa: E402
from app.providers.llm.mock import MockLLMProvider  # noqa: E402

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.attributes["database_url"] = database_url
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    cfg = alembic_config(TEST_DATABASE_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    eng = create_engine(TEST_DATABASE_URL)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        env="test",
        database_url=TEST_DATABASE_URL,
        llm_provider="mock",
        embedding_provider="mock",
        search_providers=["mock"],
        storage_dir=tmp_path / "storage",
        pipeline_execution="inline",
    )


@pytest.fixture
def mock_llm() -> MockLLMProvider:
    return MockLLMProvider()


@pytest.fixture
def mock_embeddings() -> MockEmbeddingProvider:
    return MockEmbeddingProvider()


@pytest.fixture
def client(
    db_session: Session, mock_llm: MockLLMProvider, mock_embeddings: MockEmbeddingProvider
) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    app.dependency_overrides[deps.get_llm_provider_dep] = lambda: mock_llm
    app.dependency_overrides[deps.get_embedding_provider_dep] = lambda: mock_embeddings
    with TestClient(app) as c:
        yield c


@pytest.fixture
def world(db_session):
    from tests import scenario

    return scenario.make_world(db_session)


@pytest.fixture
def api(db_session, settings, world):
    """A TestClient wired to the real DB session, the scripted mock providers and an
    inline pipeline dispatcher, plus helpers to log in as the scenario's users."""
    from app.pipeline.dispatch import InlineDispatcher
    from tests import scenario

    app = create_app()
    ctx = scenario.make_context(db_session, settings, world)
    app.dependency_overrides[deps.get_db] = lambda: db_session
    app.dependency_overrides[deps.get_settings_dep] = lambda: settings
    app.dependency_overrides[deps.get_dispatcher] = lambda: InlineDispatcher(ctx)
    app.dependency_overrides[deps.get_llm_provider_dep] = lambda: world.llm
    with TestClient(app) as c:

        def login(user):
            r = c.post(
                "/api/v1/auth/token", json={"email": user.email, "password": scenario.PASSWORD}
            )
            assert r.status_code == 200, r.text
            return {"Authorization": f"Bearer {r.json()['access_token']}"}

        c.login = login
        c.world = world
        c.ctx = ctx
        yield c
