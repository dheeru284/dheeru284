from __future__ import annotations

from app.workers.celery_app import celery_app


@celery_app.task(name="system.ping")
def ping() -> str:
    """Round-trip check for the worker and broker."""
    return "pong"
