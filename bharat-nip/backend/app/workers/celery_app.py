"""Celery application. Tasks are thin wrappers that delegate to services
(ARCHITECTURE.md §4.8). Pipeline stage tasks arrive in Phase 1."""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings


def create_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "bnip",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["app.workers.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
        result_expires=3600,
    )
    return app


celery_app = create_celery()
