"""Migrations must round-trip on an empty database and match the models
(TESTING_STRATEGY.md §3, DATABASE_DESIGN.md §6)."""

import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

import app.models  # noqa: F401
from alembic import command
from app.db.base import Base
from tests.conftest import TEST_DATABASE_URL, alembic_config


@pytest.fixture
def scratch_db_url():
    base = make_url(TEST_DATABASE_URL)
    name = f"bnip_mig_{uuid.uuid4().hex[:10]}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = base.set(database=name).render_as_string(hide_password=False)
    try:
        yield url
    finally:
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def test_upgrade_downgrade_upgrade_round_trip(scratch_db_url):
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "head")
    engine = create_engine(scratch_db_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert set(Base.metadata.tables) <= tables

        command.downgrade(cfg, "base")
        remaining = set(inspect(engine).get_table_names()) - {"alembic_version"}
        assert remaining == set()

        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            diff = compare_metadata(
                MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata
            )
        assert diff == [], f"Models and migrations differ: {diff}"
    finally:
        engine.dispose()
