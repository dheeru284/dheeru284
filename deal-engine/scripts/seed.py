"""Initialise retailers from the adapter registry. Safe to run repeatedly.
Usage: python -m scripts.seed"""
from app.database.session import session_scope
from app.services import catalog
from app.utils.logging import configure_logging

if __name__ == "__main__":
    configure_logging()
    with session_scope() as s:
        rows = catalog.sync_retailers(s)
        for r in rows:
            print(f"{r.key:18} active={r.active!s:5} status={r.status:12} {r.status_reason or ''}"[:160])
