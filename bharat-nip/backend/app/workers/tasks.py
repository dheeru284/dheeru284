from __future__ import annotations

import uuid

from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.pipeline import orchestrator
from app.pipeline.dispatch import build_context
from app.workers.celery_app import celery_app


@celery_app.task(name="system.ping")
def ping() -> str:
    """Round-trip check for the worker and broker."""
    return "pong"


@celery_app.task(name="pipeline.process_submission")
def process_submission_task(submission_id: str) -> list[str]:
    with get_sessionmaker()() as session:
        ctx = build_context(session, get_settings())
        claim_ids = orchestrator.process_submission(ctx, uuid.UUID(submission_id))
        session.commit()
        return [str(c) for c in claim_ids]


@celery_app.task(name="pipeline.process_claim")
def process_claim_task(claim_id: str) -> None:
    with get_sessionmaker()() as session:
        ctx = build_context(session, get_settings())
        orchestrator.process_claim(ctx, uuid.UUID(claim_id))
        session.commit()
