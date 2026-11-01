"""Read models: narrative detail, claim history, evidence timeline, graph and historical
claim matching. Speaker identity is not exposed in any of them."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.state import review_status_for
from app.models import (
    Assessment,
    Claim,
    Evidence,
    Narrative,
    NarrativeClaim,
    NarrativeMetric,
    NarrativeRelation,
    ReviewDecision,
    ReviewTask,
    Source,
    Submission,
    Topic,
)
from app.narratives import config as C
from app.narratives.engine import approved_verifications, display_text, load_claims
from app.narratives.similarity import TfidfSimilarity, claim_text, cosine


def latest_metrics(session: Session, narrative_id: uuid.UUID) -> NarrativeMetric | None:
    return session.scalar(
        select(NarrativeMetric)
        .where(NarrativeMetric.narrative_id == narrative_id)
        .order_by(NarrativeMetric.version.desc())
        .limit(1)
    )


def metrics_dict(m: NarrativeMetric | None) -> dict[str, Any] | None:
    if m is None:
        return None
    return {
        "computed_at": m.computed_at.isoformat(),
        "engine_version": m.engine_version,
        "claim_count": m.claim_count,
        "rate_7d": m.rate_7d,
        "acceleration": m.acceleration,
        "recurring": m.recurring,
        "evidence_status": m.evidence_status.value,
        "evidence_strength": m.evidence_strength,
        "public_interest": m.public_interest,
        "momentum": m.momentum,
        "harm_score": m.harm_score,
        "uncertainty": m.uncertainty,
        "coverage": m.coverage,
        "recommendation": m.recommendation.value,
        "suggested_status": m.suggested_status.value,
        "details": m.details,
    }


def member_claim_ids(session: Session, narrative_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(NarrativeClaim.claim_id).where(
                NarrativeClaim.narrative_id == narrative_id, NarrativeClaim.excluded.is_(False)
            )
        )
    )


def claim_history(session: Session, narrative_id: uuid.UUID) -> list[dict[str, Any]]:
    """Every member claim in time order, with its verification state and burst number."""
    ids = set(member_claim_ids(session, narrative_id))
    rows = [r for r in load_claims(session).values() if r.id in ids]
    rows.sort(key=lambda r: (r.seen_at, str(r.id)))
    verified = approved_verifications(session)
    memberships = {
        m.claim_id: m
        for m in session.scalars(
            select(NarrativeClaim).where(NarrativeClaim.narrative_id == narrative_id)
        )
    }
    out, burst, prev = [], 0, None
    for r in rows:
        if prev is None or (r.seen_at - prev).days > C.RECURRENCE_GAP_DAYS:
            burst += 1
        prev = r.seen_at
        claim = session.get(Claim, r.id)
        sub = session.get(Submission, r.submission_id)
        latest = session.scalar(
            select(Assessment)
            .where(Assessment.claim_id == r.id)
            .order_by(Assessment.revision.desc())
            .limit(1)
        )
        approved = verified.get(r.id)
        m = memberships.get(r.id)
        out.append(
            {
                "claim_id": str(r.id),
                "text": display_text(r.normalized_text),
                "seen_at": r.seen_at.isoformat(),
                "burst": burst,
                "origin": r.origin,
                "submission_type": sub.submission_type.value,
                "claim_type": claim.claim_type.value,
                "claim_status": claim.status.value,
                "review_status": review_status_for(claim.status).value,
                "latest_classification": latest.classification.value if latest else None,
                "approved_classification": approved[0].value if approved else None,
                "similarity": m.similarity if m else None,
                "added_by": m.added_by.value if m else None,
            }
        )
    return out


def evidence_timeline(session: Session, narrative_id: uuid.UUID) -> list[dict[str, Any]]:
    """Evidence documents and human decisions over time, oldest first."""
    ids = member_claim_ids(session, narrative_id)
    if not ids:
        return []
    events: list[dict[str, Any]] = []
    # The same quote from the same document often supports several claims of a narrative:
    # show it once, with the claims it supports.
    grouped: dict[tuple, dict[str, Any]] = {}
    for ev, src in session.execute(
        select(Evidence, Source)
        .join(Source, Source.id == Evidence.source_id)
        .where(Evidence.claim_id.in_(ids))
        .order_by(Evidence.created_at)
    ):
        key = (src.id, ev.quote_char_start, ev.quote_char_end, ev.stance)
        if key in grouped:
            grouped[key]["claim_ids"].append(str(ev.claim_id))
            continue
        when = src.published_at or src.retrieved_at
        grouped[key] = {
            "kind": "EVIDENCE",
            "at": when.isoformat(),
            "date_basis": "published" if src.published_at else "retrieved",
            "claim_id": str(ev.claim_id),
            "claim_ids": [str(ev.claim_id)],
            "evidence_id": str(ev.id),
            "stance": ev.stance.value,
            "quote": ev.quote,
            "source": {
                "title": src.title,
                "url": src.url,
                "publisher": src.publisher_name,
                "source_type": src.source_type.value,
                "is_primary": src.is_primary,
            },
        }
    events.extend(grouped.values())
    for dec, task in session.execute(
        select(ReviewDecision, ReviewTask)
        .join(ReviewTask, ReviewTask.id == ReviewDecision.review_task_id)
        .where(ReviewTask.claim_id.in_(ids))
    ):
        events.append(
            {
                "kind": "REVIEW_DECISION",
                "at": dec.created_at.isoformat(),
                "claim_id": str(task.claim_id),
                "decision": dec.decision.value,
                "final_classification": dec.final_classification.value
                if dec.final_classification
                else None,
            }
        )
    events.sort(key=lambda e: (e["at"], e["kind"]))
    return events


def graph(session: Session, topic_id: uuid.UUID | None = None) -> dict[str, Any]:
    narratives = list(session.scalars(select(Narrative)))
    if topic_id:
        narratives = [n for n in narratives if n.topic_id == topic_id]
    keep = {n.id for n in narratives}
    topics = {t.id: t for t in session.scalars(select(Topic))}
    nodes = []
    for n in narratives:
        m = latest_metrics(session, n.id)
        nodes.append(
            {
                "id": str(n.id),
                "title": n.title,
                "status": n.status.value,
                "topic_id": str(n.topic_id) if n.topic_id else None,
                "topic_label": topics[n.topic_id].label if n.topic_id in topics else None,
                "claim_count": m.claim_count if m else 0,
                "recommendation": m.recommendation.value if m else None,
                "evidence_status": m.evidence_status.value if m else None,
                "momentum": m.momentum if m else 0.0,
            }
        )
    edges = [
        {
            "id": str(r.id),
            "source": str(r.source_id),
            "target": str(r.target_id),
            "type": r.relation_type.value,
            "weight": r.weight,
            "details": r.details,
        }
        for r in session.scalars(select(NarrativeRelation))
        if r.source_id in keep and r.target_id in keep
    ]
    nodes.sort(key=lambda x: (x["topic_label"] or "", x["id"]))
    edges.sort(key=lambda e: (e["source"], e["target"], e["type"]))
    return {"nodes": nodes, "edges": edges}


def history_matches(session: Session, claim_id: uuid.UUID, limit: int = 10) -> list[dict]:
    """Earlier similar claims, with their human-approved classification if any."""
    claims = load_claims(session)
    target = claims.get(str(claim_id))
    if target is None:
        return []
    sim = TfidfSimilarity()
    sim.fit({k: claim_text(c.normalized_text, c.subject, c.obj) for k, c in claims.items()})
    tv = sim.vector(target.key)
    verified = approved_verifications(session)
    narrative_of = {
        m.claim_id: m.narrative_id
        for m in session.scalars(select(NarrativeClaim).where(NarrativeClaim.excluded.is_(False)))
    }
    out = []
    for k, c in claims.items():
        if c.id == target.id or (c.seen_at, k) >= (target.seen_at, target.key):
            continue
        s = cosine(tv, sim.vector(k))
        if s < C.HISTORY_MATCH_SIMILARITY:
            continue
        approved = verified.get(c.id)
        decided_at = None
        if approved:
            decided_at = session.scalar(
                select(ReviewDecision.created_at)
                .join(ReviewTask, ReviewTask.id == ReviewDecision.review_task_id)
                .where(ReviewTask.claim_id == c.id)
                .order_by(ReviewDecision.created_at.desc())
                .limit(1)
            )
        out.append(
            {
                "claim_id": str(c.id),
                "text": display_text(c.normalized_text),
                "similarity": s,
                "seen_at": c.seen_at.isoformat(),
                "approved_classification": approved[0].value if approved else None,
                "approved_at": decided_at.isoformat() if decided_at else None,
                "narrative_id": str(narrative_of[c.id]) if c.id in narrative_of else None,
            }
        )
    out.sort(key=lambda x: (-x["similarity"], x["seen_at"]))
    return out[:limit]
