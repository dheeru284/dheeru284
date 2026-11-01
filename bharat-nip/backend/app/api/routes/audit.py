from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import Admin, Analyst
from app.api.deps import get_db
from app.audit.service import AuditService
from app.models import AIRun, AuditEvent
from app.schemas.api import AIRunOut, AuditEventOut, ChainVerificationOut
from app.services.errors import NotFound

router = APIRouter(tags=["audit"])
DB = Annotated[Session, Depends(get_db)]


@router.get("/audit-events", response_model=list[AuditEventOut])
def list_events(
    _: Admin,
    db: DB,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    actor_id: str | None = None,
    after_seq: int = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    q = select(AuditEvent).where(AuditEvent.seq > after_seq).order_by(AuditEvent.seq)
    for column, value in (
        (AuditEvent.entity_type, entity_type),
        (AuditEvent.entity_id, entity_id),
        (AuditEvent.action, action),
        (AuditEvent.actor_id, actor_id),
    ):
        if value:
            q = q.where(column == value)
    return db.scalars(q.limit(limit)).all()


@router.get("/audit-events/verify", response_model=ChainVerificationOut)
def verify(_: Admin, db: DB):
    result = AuditService(db).verify_chain()
    return ChainVerificationOut(
        ok=result.ok, checked=result.checked, first_broken_seq=result.first_broken_seq
    )


@router.get("/ai-runs/{run_id}", response_model=AIRunOut)
def get_ai_run(run_id: uuid.UUID, _: Analyst, db: DB):
    run = db.get(AIRun, run_id)
    if run is None:
        raise NotFound("AI run not found.")
    return run
