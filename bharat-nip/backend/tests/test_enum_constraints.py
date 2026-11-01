"""Autogenerate cannot see CHECK constraints on non-native enums, so a migration could
silently leave a stale value list. This test compares every enum CHECK constraint in the
migrated database with the Python enum it is declared from."""

import re

from sqlalchemy import Enum, text

import app.models  # noqa: F401
from app.db.base import Base

VALUE_RE = re.compile(r"'([^']*)'::")


def _db_enum_values(session, table: str, column: str, name: str) -> set[str] | None:
    """Values of the enum CHECK constraint, found by its conventional name."""
    definition = session.scalar(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = CAST(:t AS regclass) AND contype = 'c' AND conname = :n"
        ),
        {"t": table, "n": f"ck_{table}_{name}"},
    )
    if definition is None or f"({column})::text" not in definition:
        return None
    return set(VALUE_RE.findall(definition))


def test_every_enum_check_constraint_matches_python(db_session):
    checked = 0
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if not isinstance(column.type, Enum) or column.type.native_enum:
                continue
            expected = set(column.type.enums)
            actual = _db_enum_values(db_session, table.name, column.name, column.type.name)
            assert actual is not None, f"no CHECK constraint for {table.name}.{column.name}"
            assert actual == expected, f"{table.name}.{column.name}: db={actual} py={expected}"
            checked += 1
    assert checked >= 30
