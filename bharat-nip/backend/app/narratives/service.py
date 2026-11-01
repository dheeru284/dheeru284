"""Analyst operations on narratives. Every change is audited; status and harm changes need a
note or rationale. The engine never changes status (except creating narratives as EMERGING)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.domain.enums import (
    ActorType,
    HarmCategory,
    HarmSeverity,
    MembershipSource,
    NarrativeOrigin,
    NarrativeStatus,
    ObservationMetric,
    ResponseType,
)
from app.models import (
    Claim,
    Narrative,
    NarrativeClaim,
    NarrativeObservation,
    NarrativeResponse,
    User,
)
from app.narratives.engine import display_text, load_claims
from app.narratives.recommend import STATUS_TRANSITIONS
from app.services.errors import Conflict, NotFound, Unprocessable


def _audit(session: Session, user: User, action: str, narrative_id, payload: dict) -> None:
    AuditService(session).record(
        actor_type=ActorType.USER,
        actor_id=str(user.id),
        action=action,
        entity_type="narrative",
        entity_id=narrative_id,
        payload=payload,
    )


def get_narrative(session: Session, narrative_id: uuid.UUID) -> Narrative:
    n = session.get(Narrative, narrative_id)
    if n is None:
        raise NotFound("Narrative not found.")
    return n


def create_manual(
    session: Session,
    user: User,
    claim_ids: list[uuid.UUID],
    title: str | None,
    summary: str | None,
) -> Narrative:
    if not claim_ids:
        raise Unprocessable("A narrative needs at least one claim.")
    claims = load_claims(session)
    rows = []
    for cid in dict.fromkeys(claim_ids):
        if str(cid) not in claims:
            raise NotFound(f"Claim {cid} not found.")
        if session.scalar(select(NarrativeClaim).where(NarrativeClaim.claim_id == cid)):
            raise Conflict(f"Claim {cid} already belongs to a narrative.")
        rows.append(claims[str(cid)])
    seen = [r.seen_at for r in rows]
    n = Narrative(
        title=(title or display_text(rows[0].normalized_text))[:500],
        summary=summary,
        status=NarrativeStatus.EMERGING,
        origin=NarrativeOrigin.MANUAL,
        first_seen_at=min(seen),
        last_seen_at=max(seen),
        created_by_id=user.id,
    )
    session.add(n)
    session.flush()
    for r in rows:
        session.add(
            NarrativeClaim(
                narrative_id=n.id,
                claim_id=r.id,
                added_by=MembershipSource.USER,
                added_by_user_id=user.id,
            )
        )
    session.flush()
    _audit(
        session,
        user,
        "narrative.created",
        n.id,
        {"title": n.title, "origin": "MANUAL", "claims": [str(r.id) for r in rows]},
    )
    return n


def add_claim(
    session: Session, user: User, narrative_id: uuid.UUID, claim_id: uuid.UUID, note: str | None
) -> NarrativeClaim:
    n = get_narrative(session, narrative_id)
    if session.get(Claim, claim_id) is None:
        raise NotFound("Claim not found.")
    existing = session.scalar(select(NarrativeClaim).where(NarrativeClaim.claim_id == claim_id))
    if existing is not None and not existing.excluded:
        if existing.narrative_id == n.id:
            raise Conflict("Claim is already in this narrative.")
        raise Conflict("Claim belongs to another narrative; remove it there first.")
    previous = str(existing.narrative_id) if existing else None
    if existing is not None:  # an analyst previously removed it; move it here
        existing.narrative_id = n.id
        existing.excluded = False
        existing.added_by = MembershipSource.USER
        existing.added_by_user_id = user.id
        row = existing
    else:
        row = NarrativeClaim(
            narrative_id=n.id,
            claim_id=claim_id,
            added_by=MembershipSource.USER,
            added_by_user_id=user.id,
        )
        session.add(row)
    session.flush()
    _audit(
        session,
        user,
        "narrative.claim_added",
        n.id,
        {
            "claim_id": str(claim_id),
            "by": "USER",
            "previously_excluded_from": previous,
            "note": note,
        },
    )
    return row


def remove_claim(
    session: Session, user: User, narrative_id: uuid.UUID, claim_id: uuid.UUID, note: str
) -> None:
    if not note or not note.strip():
        raise Unprocessable("Removing a claim requires a note.")
    row = session.scalar(
        select(NarrativeClaim).where(
            NarrativeClaim.claim_id == claim_id, NarrativeClaim.narrative_id == narrative_id
        )
    )
    if row is None or row.excluded:
        raise NotFound("Claim is not in this narrative.")
    row.excluded = True
    session.flush()
    _audit(
        session,
        user,
        "narrative.claim_removed",
        narrative_id,
        {"claim_id": str(claim_id), "note": note},
    )


def set_status(
    session: Session,
    user: User,
    narrative_id: uuid.UUID,
    status: NarrativeStatus,
    note: str,
    at: datetime | None = None,
) -> Narrative:
    n = get_narrative(session, narrative_id)
    if not note or not note.strip():
        raise Unprocessable("A status change requires a note.")
    if status not in STATUS_TRANSITIONS[n.status]:
        raise Conflict(f"Narrative is {n.status.value}; cannot move to {status.value}.")
    previous = n.status
    n.status = status
    n.status_note = note
    n.status_changed_by_id = user.id
    n.status_changed_at = at or datetime.now(UTC)
    session.flush()
    _audit(
        session,
        user,
        "narrative.status_changed",
        n.id,
        {"from": previous.value, "to": status.value, "note": note},
    )
    return n


def assess_harm(
    session: Session,
    user: User,
    narrative_id: uuid.UUID,
    category: HarmCategory,
    severity: HarmSeverity,
    rationale: str | None,
) -> Narrative:
    n = get_narrative(session, narrative_id)
    if severity not in (HarmSeverity.UNASSESSED, HarmSeverity.NONE) and not (
        rationale and rationale.strip()
    ):
        raise Unprocessable("A harm severity of LOW or above requires a rationale.")
    if severity in (HarmSeverity.LOW, HarmSeverity.MEDIUM, HarmSeverity.HIGH) and (
        category == HarmCategory.NONE
    ):
        raise Unprocessable("Choose the harm category this severity refers to.")
    before = {"category": n.harm_category.value, "severity": n.harm_severity.value}
    n.harm_category = category
    n.harm_severity = severity
    n.harm_rationale = rationale
    n.harm_assessed_by_id = user.id
    n.harm_assessed_at = datetime.now(UTC)
    session.flush()
    _audit(
        session,
        user,
        "narrative.harm_assessed",
        n.id,
        {
            "before": before,
            "category": category.value,
            "severity": severity.value,
            "rationale": rationale,
        },
    )
    return n


def update_text(
    session: Session, user: User, narrative_id: uuid.UUID, title: str | None, summary: str | None
) -> Narrative:
    n = get_narrative(session, narrative_id)
    changes = {}
    if title is not None and title.strip() and title != n.title:
        changes["title"] = {"from": n.title, "to": title}
        n.title = title.strip()[:500]
    if summary is not None and summary != n.summary:
        changes["summary"] = {"from": n.summary, "to": summary}
        n.summary = summary
    if changes:
        session.flush()
        _audit(session, user, "narrative.updated", n.id, changes)
    return n


def add_observation(
    session: Session,
    user: User,
    narrative_id: uuid.UUID,
    *,
    observed_at: datetime,
    channel: str,
    metric: ObservationMetric,
    value: int,
    source_url: str | None,
    note: str | None,
) -> NarrativeObservation:
    get_narrative(session, narrative_id)
    obs = NarrativeObservation(
        narrative_id=narrative_id,
        observed_at=observed_at,
        channel=channel.strip(),
        metric=metric,
        value=value,
        source_url=source_url,
        note=note,
        recorded_by_id=user.id,
    )
    session.add(obs)
    session.flush()
    _audit(
        session,
        user,
        "narrative.observation_added",
        narrative_id,
        {
            "channel": obs.channel,
            "metric": metric.value,
            "value": value,
            "observed_at": observed_at.isoformat(),
            "source_url": source_url,
        },
    )
    return obs


def add_response(
    session: Session,
    user: User,
    narrative_id: uuid.UUID,
    *,
    response_type: ResponseType,
    title: str,
    url: str | None,
    channel: str | None,
    published_at: datetime,
) -> NarrativeResponse:
    get_narrative(session, narrative_id)
    resp = NarrativeResponse(
        narrative_id=narrative_id,
        response_type=response_type,
        title=title,
        url=url,
        channel=channel,
        published_at=published_at,
        recorded_by_id=user.id,
    )
    session.add(resp)
    session.flush()
    _audit(
        session,
        user,
        "narrative.response_recorded",
        narrative_id,
        {
            "response_type": response_type.value,
            "title": title,
            "url": url,
            "published_at": published_at.isoformat(),
        },
    )
    return resp
