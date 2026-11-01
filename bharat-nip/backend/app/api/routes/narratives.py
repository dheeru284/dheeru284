"""Narrative intelligence API (NARRATIVE_INTELLIGENCE.md). Analysts and above only.

All responses describe narratives, claims, evidence and aggregate public counts. No endpoint
returns or accepts data about individual members of the public.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import Analyst
from app.api.deps import get_db, get_dispatcher
from app.domain.enums import (
    HarmCategory,
    HarmSeverity,
    NarrativeStatus,
    ObservationMetric,
    Recommendation,
    ResponseType,
)
from app.models import (
    Narrative,
    NarrativeMetric,
    NarrativeObservation,
    NarrativeRelation,
    NarrativeResponse,
    Topic,
)
from app.narratives import service
from app.narratives.queries import (
    claim_history,
    evidence_timeline,
    graph,
    history_matches,
    latest_metrics,
    metrics_dict,
)
from app.narratives.recommend import STATUS_TRANSITIONS
from app.pipeline.dispatch import PipelineDispatcher
from app.services.errors import NotFound

router = APIRouter(tags=["narratives"])
DB = Annotated[Session, Depends(get_db)]

PRIORITY = {
    Recommendation.ESCALATE: 0,
    Recommendation.CORRECT: 1,
    Recommendation.INVESTIGATE: 2,
    Recommendation.RESPOND: 3,
    Recommendation.MONITOR: 4,
    Recommendation.IGNORE: 5,
}


# --- schemas -----------------------------------------------------------------------------


class NarrativeCreate(BaseModel):
    claim_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=500)
    summary: str | None = Field(default=None, max_length=5000)


class NarrativeUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    summary: str | None = Field(default=None, max_length=5000)


class StatusIn(BaseModel):
    status: NarrativeStatus
    note: str = Field(min_length=3, max_length=5000)


class HarmIn(BaseModel):
    category: HarmCategory
    severity: HarmSeverity
    rationale: str | None = Field(default=None, max_length=5000)


class MemberIn(BaseModel):
    claim_id: uuid.UUID
    note: str | None = Field(default=None, max_length=2000)


class MemberRemove(BaseModel):
    note: str = Field(min_length=3, max_length=2000)


class ObservationIn(BaseModel):
    """An aggregate public count. There are deliberately no fields for individuals."""

    observed_at: datetime
    channel: str = Field(min_length=1, max_length=100)
    metric: ObservationMetric
    value: int = Field(ge=0, le=10**12)
    source_url: str | None = Field(default=None, max_length=2048)
    note: str | None = Field(default=None, max_length=2000)


class ResponseIn(BaseModel):
    response_type: ResponseType
    title: str = Field(min_length=1, max_length=500)
    url: str | None = Field(default=None, max_length=2048)
    channel: str | None = Field(default=None, max_length=100)
    published_at: datetime


# --- helpers -----------------------------------------------------------------------------


def _summary(db: Session, n: Narrative, topics: dict[uuid.UUID, Topic]) -> dict[str, Any]:
    m = latest_metrics(db, n.id)
    return {
        "id": str(n.id),
        "title": n.title,
        "status": n.status.value,
        "origin": n.origin.value,
        "topic": {"id": str(n.topic_id), "label": topics[n.topic_id].label}
        if n.topic_id in topics
        else None,
        "first_seen_at": n.first_seen_at.isoformat(),
        "last_seen_at": n.last_seen_at.isoformat(),
        "harm_category": n.harm_category.value,
        "harm_severity": n.harm_severity.value,
        "metrics": metrics_dict(m),
    }


def _observation(o: NarrativeObservation) -> dict[str, Any]:
    return {
        "id": str(o.id),
        "observed_at": o.observed_at.isoformat(),
        "channel": o.channel,
        "metric": o.metric.value,
        "value": o.value,
        "source_url": o.source_url,
        "note": o.note,
    }


def _response(r: NarrativeResponse) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "response_type": r.response_type.value,
        "title": r.title,
        "url": r.url,
        "channel": r.channel,
        "published_at": r.published_at.isoformat(),
    }


# --- read --------------------------------------------------------------------------------


@router.get("/narratives")
def list_narratives(
    _: Analyst,
    db: DB,
    status: NarrativeStatus | None = None,
    recommendation: Recommendation | None = None,
    topic_id: uuid.UUID | None = None,
    include_archived: bool = False,
) -> dict[str, Any]:
    """Dashboard data: narratives sorted by recommendation priority, then momentum."""
    topics = {t.id: t for t in db.scalars(select(Topic))}
    q = select(Narrative)
    if status:
        q = q.where(Narrative.status == status)
    elif not include_archived:
        q = q.where(Narrative.status != NarrativeStatus.ARCHIVED)
    if topic_id:
        q = q.where(Narrative.topic_id == topic_id)
    items = [_summary(db, n, topics) for n in db.scalars(q)]
    if recommendation:
        items = [
            i for i in items if i["metrics"] and i["metrics"]["recommendation"] == recommendation
        ]

    def key(i):
        m = i["metrics"]
        if not m:
            return (9, 0.0, i["id"])
        return (PRIORITY[Recommendation(m["recommendation"])], -m["momentum"], i["id"])

    items.sort(key=key)
    counts = {
        "by_status": {s.value: 0 for s in NarrativeStatus},
        "by_recommendation": {r.value: 0 for r in Recommendation},
    }
    for n in db.scalars(select(Narrative)):
        counts["by_status"][n.status.value] += 1
    for i in items:
        if i["metrics"]:
            counts["by_recommendation"][i["metrics"]["recommendation"]] += 1
    emerging = [
        {
            "id": str(t.id),
            "label": t.label,
            "keywords": t.keywords,
            "recent_count": t.recent_count,
            "baseline_weekly": t.baseline_weekly,
            "emerging_since": t.emerging_since.isoformat() if t.emerging_since else None,
        }
        for t in topics.values()
        if t.is_emerging
    ]
    emerging.sort(key=lambda t: (-t["recent_count"], t["label"]))
    return {"items": items, "counts": counts, "emerging_topics": emerging}


@router.get("/narratives/graph")
def get_graph(_: Analyst, db: DB, topic_id: uuid.UUID | None = None) -> dict[str, Any]:
    return graph(db, topic_id)


@router.get("/topics")
def list_topics(_: Analyst, db: DB) -> list[dict[str, Any]]:
    topics = db.scalars(select(Topic).where(Topic.claim_count > 0)).all()
    return sorted(
        (
            {
                "id": str(t.id),
                "label": t.label,
                "keywords": t.keywords,
                "claim_count": t.claim_count,
                "recent_count": t.recent_count,
                "baseline_weekly": t.baseline_weekly,
                "is_emerging": t.is_emerging,
                "emerging_since": t.emerging_since.isoformat() if t.emerging_since else None,
            }
            for t in topics
        ),
        key=lambda t: (not t["is_emerging"], -t["recent_count"], t["label"]),
    )


@router.get("/narratives/{narrative_id}")
def get_narrative(narrative_id: uuid.UUID, _: Analyst, db: DB) -> dict[str, Any]:
    n = service.get_narrative(db, narrative_id)
    topics = {t.id: t for t in db.scalars(select(Topic))}
    related = []
    for r in db.scalars(
        select(NarrativeRelation).where(
            (NarrativeRelation.source_id == n.id) | (NarrativeRelation.target_id == n.id)
        )
    ):
        other = r.target_id if r.source_id == n.id else r.source_id
        o = db.get(Narrative, other)
        related.append(
            {
                "narrative_id": str(other),
                "title": o.title,
                "status": o.status.value,
                "type": r.relation_type.value,
                "weight": r.weight,
                "details": r.details,
            }
        )
    related.sort(key=lambda x: (-x["weight"], x["type"]))
    return {
        **_summary(db, n, topics),
        "summary": n.summary,
        "harm_rationale": n.harm_rationale,
        "harm_assessed_at": n.harm_assessed_at.isoformat() if n.harm_assessed_at else None,
        "status_note": n.status_note,
        "status_changed_at": n.status_changed_at.isoformat() if n.status_changed_at else None,
        "allowed_status_transitions": sorted(s.value for s in STATUS_TRANSITIONS[n.status]),
        "related": related,
        "observations": [
            _observation(o)
            for o in db.scalars(
                select(NarrativeObservation)
                .where(NarrativeObservation.narrative_id == n.id)
                .order_by(NarrativeObservation.observed_at)
            )
        ],
        "responses": [
            _response(r)
            for r in db.scalars(
                select(NarrativeResponse)
                .where(NarrativeResponse.narrative_id == n.id)
                .order_by(NarrativeResponse.published_at)
            )
        ],
    }


@router.get("/narratives/{narrative_id}/claims")
def get_claim_history(narrative_id: uuid.UUID, _: Analyst, db: DB) -> list[dict[str, Any]]:
    service.get_narrative(db, narrative_id)
    return claim_history(db, narrative_id)


@router.get("/narratives/{narrative_id}/evidence-timeline")
def get_evidence_timeline(narrative_id: uuid.UUID, _: Analyst, db: DB) -> list[dict[str, Any]]:
    service.get_narrative(db, narrative_id)
    return evidence_timeline(db, narrative_id)


@router.get("/narratives/{narrative_id}/metrics")
def get_metrics_history(
    narrative_id: uuid.UUID, _: Analyst, db: DB, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[dict[str, Any]]:
    service.get_narrative(db, narrative_id)
    rows = db.scalars(
        select(NarrativeMetric)
        .where(NarrativeMetric.narrative_id == narrative_id)
        .order_by(NarrativeMetric.version.desc())
        .limit(limit)
    ).all()
    return [{**metrics_dict(m), "version": m.version} for m in reversed(rows)]


@router.get("/claims/{claim_id}/history")
def get_history_matches(claim_id: uuid.UUID, _: Analyst, db: DB) -> list[dict[str, Any]]:
    """Earlier similar claims (historical claim matching), with approved classifications."""
    from app.models import Claim

    if db.get(Claim, claim_id) is None:
        raise NotFound("Claim not found.")
    return history_matches(db, claim_id)


# --- write -------------------------------------------------------------------------------


@router.post("/narratives/analyze", status_code=202)
def analyze(
    _: Analyst, dispatcher: Annotated[PipelineDispatcher, Depends(get_dispatcher)]
) -> dict[str, str]:
    """Run the narrative engine now (on a worker, or inline in inline mode)."""
    dispatcher.analyze_narratives()
    return {"status": "accepted"}


@router.post("/narratives", status_code=201)
def create_narrative(body: NarrativeCreate, user: Analyst, db: DB) -> dict[str, Any]:
    n = service.create_manual(db, user, body.claim_ids, body.title, body.summary)
    db.commit()
    return {"id": str(n.id), "title": n.title, "status": n.status.value}


@router.patch("/narratives/{narrative_id}")
def update_narrative(narrative_id: uuid.UUID, body: NarrativeUpdate, user: Analyst, db: DB):
    n = service.update_text(db, user, narrative_id, body.title, body.summary)
    db.commit()
    return {"id": str(n.id), "title": n.title, "summary": n.summary}


@router.post("/narratives/{narrative_id}/status")
def change_status(narrative_id: uuid.UUID, body: StatusIn, user: Analyst, db: DB):
    n = service.set_status(db, user, narrative_id, body.status, body.note)
    db.commit()
    return {"id": str(n.id), "status": n.status.value}


@router.put("/narratives/{narrative_id}/harm")
def assess_harm(narrative_id: uuid.UUID, body: HarmIn, user: Analyst, db: DB):
    n = service.assess_harm(db, user, narrative_id, body.category, body.severity, body.rationale)
    db.commit()
    return {"harm_category": n.harm_category.value, "harm_severity": n.harm_severity.value}


@router.post("/narratives/{narrative_id}/claims", status_code=201)
def add_member(narrative_id: uuid.UUID, body: MemberIn, user: Analyst, db: DB):
    service.add_claim(db, user, narrative_id, body.claim_id, body.note)
    db.commit()
    return {"narrative_id": str(narrative_id), "claim_id": str(body.claim_id)}


@router.post("/narratives/{narrative_id}/claims/{claim_id}/remove")
def remove_member(
    narrative_id: uuid.UUID, claim_id: uuid.UUID, body: MemberRemove, user: Analyst, db: DB
):
    service.remove_claim(db, user, narrative_id, claim_id, body.note)
    db.commit()
    return {"narrative_id": str(narrative_id), "claim_id": str(claim_id), "excluded": True}


@router.post("/narratives/{narrative_id}/observations", status_code=201)
def add_observation(narrative_id: uuid.UUID, body: ObservationIn, user: Analyst, db: DB):
    o = service.add_observation(db, user, narrative_id, **body.model_dump())
    db.commit()
    return _observation(o)


@router.post("/narratives/{narrative_id}/responses", status_code=201)
def add_response(narrative_id: uuid.UUID, body: ResponseIn, user: Analyst, db: DB):
    r = service.add_response(db, user, narrative_id, **body.model_dump())
    db.commit()
    return _response(r)
