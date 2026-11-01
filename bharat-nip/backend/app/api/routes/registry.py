from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.auth import Admin, Analyst
from app.api.deps import get_db
from app.models import Entity, RegistrySource, Source
from app.schemas.api import (
    EntityCreate,
    EntityOut,
    Page,
    RegistryIn,
    RegistryOut,
    RegistryUpdate,
    SourceCreated,
    SourceDetail,
    SourceIn,
    SourceOut,
    VerificationIn,
    decode_cursor,
    encode_cursor,
)
from app.services import registry as registry_service
from app.services.errors import NotFound
from app.services.sources import store_source

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]


# --- entities ----------------------------------------------------------------------------


@router.get("/entities", response_model=list[EntityOut], tags=["entities"])
def list_entities(_: Analyst, db: DB, q: str | None = None):
    query = select(Entity).order_by(Entity.name)
    if q:
        query = query.where(Entity.name.ilike(f"%{q}%"))
    return db.scalars(query.limit(200)).all()


@router.post("/entities", response_model=EntityOut, status_code=201, tags=["entities"])
def create_entity(body: EntityCreate, user: Analyst, db: DB):
    from app.audit.service import AuditService
    from app.domain.enums import ActorType

    entity = Entity(**body.model_dump())
    db.add(entity)
    db.flush()
    AuditService(db).record(
        actor_type=ActorType.USER,
        actor_id=str(user.id),
        action="entity.created",
        entity_type="entity",
        entity_id=entity.id,
        payload=body.model_dump(mode="json"),
    )
    db.commit()
    return entity


# --- source registry ---------------------------------------------------------------------


@router.get("/registry", response_model=list[RegistryOut], tags=["registry"])
def list_registry(_: Analyst, db: DB):
    return db.scalars(select(RegistrySource).order_by(RegistrySource.name)).all()


@router.post("/registry", response_model=RegistryOut, status_code=201, tags=["registry"])
def create_registry_entry(body: RegistryIn, admin: Admin, db: DB):
    entry = registry_service.create_entry(db, admin, body.model_dump())
    db.commit()
    return entry


@router.patch("/registry/{entry_id}", response_model=RegistryOut, tags=["registry"])
def update_registry_entry(entry_id: uuid.UUID, body: RegistryUpdate, admin: Admin, db: DB):
    entry = registry_service.update_entry(db, admin, entry_id, body.model_dump(exclude_unset=True))
    db.commit()
    return entry


@router.post("/registry/{entry_id}/verification", response_model=RegistryOut, tags=["registry"])
def verify_registry_entry(entry_id: uuid.UUID, body: VerificationIn, admin: Admin, db: DB):
    entry = registry_service.set_verification(
        db,
        admin,
        entry_id,
        status=body.status,
        method=body.method,
        notes=body.notes,
        review_period_days=body.review_period_days,
    )
    db.commit()
    return entry


# --- sources (document snapshots) --------------------------------------------------------


@router.post("/sources", response_model=SourceCreated, status_code=201, tags=["sources"])
def ingest_source(body: SourceIn, user: Analyst, db: DB):
    """Add a document to the local corpus (searchable by the local_corpus provider)."""
    source, created = store_source(
        db,
        title=body.title,
        content_text=body.content_text,
        url=body.url,
        publisher_name=body.publisher_name,
        published_at=body.published_at,
        source_type=body.source_type,
        language=body.language,
        retrieval_provider="human_ingest",
        ingested_by=user,
    )
    db.commit()
    payload = SourceCreated(source=SourceOut.model_validate(source), created=created)
    return JSONResponse(
        status_code=201 if created else 200, content=payload.model_dump(mode="json")
    )


@router.get("/sources", response_model=Page[SourceOut], tags=["sources"])
def list_sources(
    _: Analyst,
    db: DB,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
):
    offset = decode_cursor(cursor)
    query = select(Source).order_by(Source.created_at.desc(), Source.id)
    if q:
        query = query.where(or_(Source.title.ilike(f"%{q}%"), Source.url.ilike(f"%{q}%")))
    rows = db.scalars(query.offset(offset).limit(limit + 1)).all()
    return Page(
        items=[SourceOut.model_validate(s) for s in rows[:limit]],
        next_cursor=encode_cursor(offset + limit) if len(rows) > limit else None,
    )


@router.get("/sources/{source_id}", response_model=SourceDetail, tags=["sources"])
def get_source(source_id: uuid.UUID, _: Analyst, db: DB):
    source = db.get(Source, source_id)
    if source is None:
        raise NotFound("Source not found.")
    return source
