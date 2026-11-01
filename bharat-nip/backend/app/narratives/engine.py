"""The narrative engine run (NARRATIVE_INTELLIGENCE.md §4).

Deterministic and idempotent: the same data produces the same narratives, topics, relations,
metrics and recommendations. Inputs are claims (blinded text), their public origins,
human-approved fact-checks, evidence, and aggregate observations. There are no inputs about
individual members of the public, and none about which party a narrative helps.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.domain.enums import (
    NON_CHECKABLE_VERDICT,
    ActorType,
    ClaimType,
    Classification,
    EntityRole,
    EntityType,
    EvidenceStatus,
    MembershipSource,
    NarrativeOrigin,
    NarrativeStatus,
    ReviewDecisionType,
    SourceType,
)
from app.domain.text import strip_placeholders
from app.models import (
    Assessment,
    Claim,
    Evidence,
    Narrative,
    NarrativeClaim,
    NarrativeMetric,
    NarrativeObservation,
    NarrativeRelation,
    NarrativeResponse,
    ReviewDecision,
    ReviewTask,
    Source,
    Submission,
    Topic,
    TopicClaim,
)
from app.narratives import config as C
from app.narratives import metrics as M
from app.narratives.recommend import RecommendationInputs, recommend, suggest_status
from app.narratives.similarity import (
    TfidfSimilarity,
    Vector,
    centroid,
    claim_text,
    cosine,
    greedy_cluster,
    label_terms,
)
from app.services.registry import normalize_domain

ACTOR = "system:narrative_engine"
LOCK_KEY = 0x4E415252  # "NARR"
_REPORTING = re.compile(
    r"^(?:said|says|claimed|claims|stated|states|announced|alleged|added)(?:\s+that)?\s+",
    re.IGNORECASE,
)
RELATION_ENTITY_TYPES = {
    EntityType.PERSON.value,
    EntityType.ORGANIZATION.value,
    EntityType.GOVERNMENT_BODY.value,
    EntityType.MEDIA_OUTLET.value,
}
RELATION_ENTITY_ROLES = {EntityRole.SUBJECT.value, EntityRole.MENTIONED.value}


@dataclass
class ClaimRow:
    id: uuid.UUID
    submission_id: uuid.UUID
    normalized_text: str
    subject: str
    obj: str
    claim_type: ClaimType
    seen_at: datetime
    origin: str | None
    entities: list[dict]

    @property
    def key(self) -> str:
        return str(self.id)

    @property
    def checkable(self) -> bool:
        return self.claim_type not in NON_CHECKABLE_VERDICT


@dataclass
class EngineReport:
    claims: int = 0
    narratives_created: list[uuid.UUID] = field(default_factory=list)
    claims_assigned: int = 0
    topics: int = 0
    emerging_topics: int = 0
    relations: int = 0
    snapshots_written: int = 0
    recommendation_changes: int = 0

    def as_dict(self) -> dict:
        return {
            "claims": self.claims,
            "narratives_created": [str(i) for i in self.narratives_created],
            "claims_assigned": self.claims_assigned,
            "topics": self.topics,
            "emerging_topics": self.emerging_topics,
            "relations": self.relations,
            "snapshots_written": self.snapshots_written,
            "recommendation_changes": self.recommendation_changes,
        }


def display_text(normalized_text: str) -> str:
    """Speaker-free title text: placeholders and leading reporting verbs removed."""
    t = " ".join(strip_placeholders(normalized_text).split())
    t = _REPORTING.sub("", t)
    return (t[:1].upper() + t[1:])[:500] if t else "(untitled narrative)"


def _as_datetime(d: date) -> datetime:
    return datetime.combine(d, time(12, 0), tzinfo=UTC)


def load_claims(session: Session) -> dict[str, ClaimRow]:
    rows = session.execute(
        select(Claim, Submission).join(Submission, Submission.id == Claim.submission_id)
    ).all()
    out: dict[str, ClaimRow] = {}
    for c, s in rows:
        seen = s.published_at or (_as_datetime(c.statement_date) if c.statement_date else None)
        seen = seen or s.created_at
        origin = normalize_domain(s.source_url) or (
            s.publisher_name.strip().lower() if s.publisher_name else None
        )
        row = ClaimRow(
            id=c.id,
            submission_id=c.submission_id,
            normalized_text=c.normalized_text,
            subject=c.subject,
            obj=c.object_,
            claim_type=c.claim_type,
            seen_at=seen,
            origin=origin,
            entities=c.entities or [],
        )
        out[row.key] = row
    return out


def approved_verifications(session: Session) -> dict[uuid.UUID, tuple[Classification, float]]:
    """Latest human APPROVE decision per claim: (final classification, assessment confidence)."""
    rows = session.execute(
        select(ReviewTask.claim_id, ReviewDecision.final_classification, Assessment.confidence)
        .join(ReviewDecision, ReviewDecision.review_task_id == ReviewTask.id)
        .join(Assessment, Assessment.id == ReviewTask.assessment_id)
        .where(ReviewDecision.decision == ReviewDecisionType.APPROVE)
        .order_by(ReviewDecision.created_at)
    ).all()
    out: dict[uuid.UUID, tuple[Classification, float]] = {}
    for claim_id, final, conf in rows:
        out[claim_id] = (final, conf)  # later rows overwrite earlier ones
    return out


def run_engine(session: Session, now: datetime | None = None) -> EngineReport:
    now = now or datetime.now(UTC)
    session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": LOCK_KEY})
    audit = AuditService(session)
    report = EngineReport()

    claims = load_claims(session)
    report.claims = len(claims)
    sim = TfidfSimilarity()
    sim.fit({k: claim_text(c.normalized_text, c.subject, c.obj) for k, c in claims.items()})
    vec = {k: sim.vector(k) for k in claims}

    # --- 1. assign unassigned claims to existing narratives --------------------------------
    narratives = {n.id: n for n in session.scalars(select(Narrative))}
    memberships = list(session.scalars(select(NarrativeClaim)))
    members: dict[uuid.UUID, list[str]] = defaultdict(list)
    taken: set[str] = set()
    for m in memberships:
        taken.add(str(m.claim_id))
        if not m.excluded:
            members[m.narrative_id].append(str(m.claim_id))
    centroids: dict[uuid.UUID, Vector] = {
        nid: centroid(vec[k] for k in ks if k in vec) for nid, ks in members.items()
    }
    order = sorted((k for k in claims if k not in taken), key=lambda k: (claims[k].seen_at, k))
    pool: list[str] = []
    for k in order:
        best, best_sim = None, C.NARRATIVE_SIMILARITY
        for nid in sorted(centroids, key=str):
            s = cosine(vec[k], centroids[nid])
            if s >= best_sim:
                best, best_sim = nid, s
        if best is None:
            pool.append(k)
            continue
        _add_member(session, audit, best, claims[k], best_sim)
        members[best].append(k)
        centroids[best] = centroid(vec[x] for x in members[best])
        report.claims_assigned += 1

    # --- 2. detect new narratives -----------------------------------------------------------
    for cluster in greedy_cluster(pool, vec, C.NARRATIVE_SIMILARITY):
        subs = {claims[k].submission_id for k in cluster}
        if len(cluster) < C.MIN_NARRATIVE_CLAIMS or len(subs) < C.MIN_NARRATIVE_SUBMISSIONS:
            continue
        cen = centroid(vec[k] for k in cluster)
        central = max(cluster, key=lambda k: (cosine(vec[k], cen), k))
        seen = [claims[k].seen_at for k in cluster]
        n = Narrative(
            title=display_text(claims[central].normalized_text),
            status=NarrativeStatus.EMERGING,
            origin=NarrativeOrigin.DETECTED,
            first_seen_at=min(seen),
            last_seen_at=max(seen),
        )
        session.add(n)
        session.flush()
        audit.record(
            actor_type=ActorType.SYSTEM,
            actor_id=ACTOR,
            action="narrative.created",
            entity_type="narrative",
            entity_id=n.id,
            payload={"title": n.title, "claims": cluster, "engine_version": C.ENGINE_VERSION},
        )
        for k in cluster:
            _add_member(session, audit, n.id, claims[k], cosine(vec[k], cen), quiet=True)
        narratives[n.id] = n
        members[n.id] = list(cluster)
        centroids[n.id] = cen
        report.narratives_created.append(n.id)

    # --- 3. topics --------------------------------------------------------------------------
    topic_of_claim = _update_topics(session, audit, claims, vec, now, report)
    for nid, ks in members.items():
        votes = Counter(topic_of_claim[k] for k in ks if k in topic_of_claim)
        narratives[nid].topic_id = (
            sorted(votes.items(), key=lambda kv: (-kv[1], str(kv[0])))[0][0] if votes else None
        )

    # --- 4. metrics and recommendations -----------------------------------------------------
    verifications = approved_verifications(session)
    statuses: dict[uuid.UUID, EvidenceStatus] = {}
    for nid in sorted(narratives, key=str):
        ks = [k for k in members.get(nid, []) if k in claims]
        statuses[nid] = _snapshot(
            session, audit, narratives[nid], [claims[k] for k in ks], verifications, now, report
        )

    # --- 5. relations -----------------------------------------------------------------------
    report.relations = _update_relations(session, narratives, members, centroids, claims, statuses)

    session.flush()
    audit.record(
        actor_type=ActorType.SYSTEM,
        actor_id=ACTOR,
        action="narrative_engine.run",
        entity_type="narrative_engine",
        entity_id=C.ENGINE_VERSION,
        payload={**report.as_dict(), "now": now.isoformat()},
    )
    return report


def _add_member(session, audit, narrative_id, claim: ClaimRow, similarity, quiet=False) -> None:
    session.add(
        NarrativeClaim(
            narrative_id=narrative_id,
            claim_id=claim.id,
            similarity=round(similarity, 4),
            added_by=MembershipSource.ENGINE,
        )
    )
    session.flush()
    if not quiet:
        audit.record(
            actor_type=ActorType.SYSTEM,
            actor_id=ACTOR,
            action="narrative.claim_added",
            entity_type="narrative",
            entity_id=narrative_id,
            payload={"claim_id": str(claim.id), "similarity": round(similarity, 4)},
        )


def _update_topics(session, audit, claims, vec, now, report) -> dict[str, uuid.UUID]:
    order = sorted(claims, key=lambda k: (claims[k].seen_at, k))
    clusters = greedy_cluster(order, vec, C.TOPIC_SIMILARITY)
    existing = list(session.scalars(select(Topic)))
    old_sets: dict[uuid.UUID, set[str]] = defaultdict(set)
    for tc in session.scalars(select(TopicClaim)):
        old_sets[tc.topic_id].add(str(tc.claim_id))
    session.execute(delete(TopicClaim))

    used: set[uuid.UUID] = set()
    topic_of_claim: dict[str, uuid.UUID] = {}
    window = timedelta(days=C.EMERGING_WINDOW_DAYS)
    for cluster in sorted(clusters, key=lambda cl: (-len(cl), cl[0])):
        cset = set(cluster)
        best, best_j = None, C.TOPIC_JACCARD_STABILITY
        for t in existing:
            if t.id in used or not old_sets.get(t.id):
                continue
            j = len(cset & old_sets[t.id]) / len(cset | old_sets[t.id])
            if j >= best_j:
                best, best_j = t, j
        cen = centroid(vec[k] for k in cluster)
        keywords = label_terms(cen, 5)
        if best is None:
            best = Topic(label=" / ".join(keywords[:3]) or "untitled")
            session.add(best)
            session.flush()
            audit.record(
                actor_type=ActorType.SYSTEM,
                actor_id=ACTOR,
                action="topic.created",
                entity_type="topic",
                entity_id=best.id,
                payload={"label": best.label, "claims": len(cluster)},
            )
        used.add(best.id)
        best.label = " / ".join(keywords[:3]) or best.label
        best.keywords = keywords
        seen = [claims[k].seen_at for k in cluster]
        recent = sum(1 for t in seen if now - window < t <= now)
        base_start = now - window * (C.EMERGING_BASELINE_WEEKS + 1)
        baseline = sum(1 for t in seen if base_start < t <= now - window)
        best.claim_count = len(cluster)
        best.recent_count = recent
        best.baseline_weekly = round(baseline / C.EMERGING_BASELINE_WEEKS, 4)
        is_emerging = M.emerging(recent, best.baseline_weekly)
        if is_emerging and not best.is_emerging:
            best.emerging_since = now
        best.is_emerging = is_emerging
        report.emerging_topics += int(is_emerging)
        for k in cluster:
            session.add(TopicClaim(claim_id=claims[k].id, topic_id=best.id))
            topic_of_claim[k] = best.id
    for t in existing:
        if t.id not in used:
            t.claim_count = t.recent_count = 0
            t.is_emerging = False
    report.topics = len(used)
    session.flush()
    return topic_of_claim


SNAPSHOT_FIELDS = (
    "claim_count",
    "rate_7d",
    "acceleration",
    "recurring",
    "evidence_status",
    "evidence_strength",
    "public_interest",
    "momentum",
    "harm_score",
    "uncertainty",
    "coverage",
    "recommendation",
    "suggested_status",
)


def _snapshot(
    session, audit, narrative: Narrative, rows: list[ClaimRow], verifications, now, report
) -> EvidenceStatus:
    ids = [r.id for r in rows]
    occurrences = [r.seen_at for r in rows if r.seen_at <= now]
    if rows:
        narrative.first_seen_at = min(r.seen_at for r in rows)
        narrative.last_seen_at = max(r.seen_at for r in rows)

    v = M.velocity(occurrences, now)
    n_bursts = M.bursts(occurrences)
    points = [
        M.ObservationPoint(o.channel, o.metric, o.observed_at, o.value)
        for o in session.scalars(
            select(NarrativeObservation).where(NarrativeObservation.narrative_id == narrative.id)
        )
    ]
    growth = M.observation_growth(points, now)
    momentum = M.momentum(v, growth)

    checks = [
        M.ClaimVerification(
            r.checkable,
            verifications.get(r.id, (None, None))[0],
            verifications.get(r.id, (None, None))[1],
        )
        for r in rows
    ]
    ev_status = M.evidence_status(checks)
    strength = M.evidence_strength(checks, ev_status)

    indicators = M.InterestIndicators(
        distinct_submissions=len({r.submission_id for r in rows}),
        distinct_origins=len({r.origin for r in rows if r.origin}),
        channels=len({p.channel for p in points}),
        reach=M.latest_reach(points, now),
    )
    interest = indicators.score()
    harm = M.harm_score(narrative.harm_severity)
    unc = M.uncertainty(checks, ev_status, narrative.harm_severity)
    responses = [
        M.ResponseRecord(r.response_type, r.published_at)
        for r in session.scalars(
            select(NarrativeResponse).where(NarrativeResponse.narrative_id == narrative.id)
        )
    ]
    external = bool(
        ids
        and session.scalar(
            select(Evidence.id)
            .join(Source, Source.id == Evidence.source_id)
            .where(Evidence.claim_id.in_(ids), Source.source_type == SourceType.FACT_CHECK)
            .limit(1)
        )
    )
    cov = M.coverage(responses, external, occurrences)

    inputs = RecommendationInputs(
        evidence_status=ev_status,
        public_relevance=interest,
        momentum=momentum,
        harm_severity=narrative.harm_severity,
        uncertainty=unc,
        coverage=cov.score,
    )
    rec = recommend(inputs)
    suggested = suggest_status(rec, inputs, narrative.last_seen_at, now)
    reactivated = bool(
        narrative.status in (NarrativeStatus.RESOLVED, NarrativeStatus.ARCHIVED)
        and narrative.status_changed_at
        and any(t > narrative.status_changed_at for t in occurrences)
    )
    values = {
        "claim_count": len(rows),
        "rate_7d": v.rate_7d,
        "acceleration": v.acceleration,
        "recurring": n_bursts >= 2,
        "evidence_status": ev_status,
        "evidence_strength": strength,
        "public_interest": interest,
        "momentum": momentum,
        "harm_score": harm,
        "uncertainty": unc,
        "coverage": cov.score,
        "recommendation": rec.recommendation,
        "suggested_status": suggested,
    }
    details = {
        "velocity": {
            "count_24h": v.count_24h,
            "count_7d": v.count_7d,
            "count_prev_7d": v.count_prev_7d,
            "rate_24h": v.rate_24h,
        },
        "bursts": n_bursts,
        "observation_growth": growth,
        "public_interest_indicators": {
            "distinct_submissions": indicators.distinct_submissions,
            "distinct_origins": indicators.distinct_origins,
            "channels": indicators.channels,
            "reach": indicators.reach,
        },
        "levels": {
            "public_relevance": M.level(interest),
            "momentum": M.level(momentum),
        },
        "verification": {
            "checkable_claims": sum(1 for c in checks if c.checkable),
            "approved": sum(1 for c in checks if c.checkable and c.approved_classification),
            "approved_classifications": sorted(
                {c.approved_classification.value for c in checks if c.approved_classification}
            ),
        },
        "coverage": {"components": cov.components, "stale": cov.stale},
        "harm": {
            "category": narrative.harm_category.value,
            "severity": narrative.harm_severity.value,
            "signals": M.harm_signals(r.normalized_text for r in rows),
        },
        "reactivated": reactivated,
        "recommendation": {**rec.to_dict(), "version": C.RECOMMENDATION_VERSION},
    }
    last = session.scalar(
        select(NarrativeMetric)
        .where(NarrativeMetric.narrative_id == narrative.id)
        .order_by(NarrativeMetric.version.desc())
        .limit(1)
    )
    unchanged = (
        last is not None
        and all(getattr(last, f) == values[f] for f in SNAPSHOT_FIELDS)
        and last.details.get("reactivated") == reactivated
    )
    if not unchanged:
        session.add(
            NarrativeMetric(
                narrative_id=narrative.id,
                version=(last.version + 1) if last else 1,
                computed_at=now,
                engine_version=C.ENGINE_VERSION,
                details=details,
                **values,
            )
        )
        report.snapshots_written += 1
        if last is None or last.recommendation != rec.recommendation:
            report.recommendation_changes += 1
            audit.record(
                actor_type=ActorType.SYSTEM,
                actor_id=ACTOR,
                action="narrative.recommendation_changed",
                entity_type="narrative",
                entity_id=narrative.id,
                payload={
                    "from": last.recommendation.value if last else None,
                    "to": rec.recommendation.value,
                    "rule": rec.rule,
                    "rationale": rec.rationale,
                    "suggested_status": suggested.value,
                    "inputs": {
                        "evidence_status": ev_status.value,
                        "public_relevance": interest,
                        "momentum": momentum,
                        "harm_severity": narrative.harm_severity.value,
                        "uncertainty": unc,
                        "coverage": cov.score,
                    },
                },
            )
    return ev_status


def _entity_keys(rows: list[ClaimRow]) -> set[str]:
    keys = set()
    for r in rows:
        for e in r.entities:
            if e.get("role") in RELATION_ENTITY_ROLES and e.get("type") in RELATION_ENTITY_TYPES:
                keys.add(str(e.get("name", "")).strip().lower())
    keys.discard("")
    return keys


def _update_relations(session, narratives, members, centroids, claims, statuses) -> int:
    session.execute(delete(NarrativeRelation))
    ids = sorted(narratives, key=str)
    rows = {nid: [claims[k] for k in members.get(nid, []) if k in claims] for nid in ids}
    entities = {nid: _entity_keys(rows[nid]) for nid in ids}
    sources: dict[uuid.UUID, set[uuid.UUID]] = {}
    for nid in ids:
        cids = [r.id for r in rows[nid]]
        sources[nid] = (
            set(session.scalars(select(Evidence.source_id).where(Evidence.claim_id.in_(cids))))
            if cids
            else set()
        )
    shared_counts = {}
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            shared_counts[(a, b)] = len(sources[a] & sources[b])
    max_shared = max(shared_counts.values(), default=0)

    count = 0

    def add(a, b, rtype, weight, details):
        nonlocal count
        lo, hi = sorted((a, b), key=str)
        session.add(
            NarrativeRelation(
                source_id=lo,
                target_id=hi,
                relation_type=rtype,
                weight=round(weight, 4),
                details=details,
            )
        )
        count += 1

    from app.domain.enums import RelationType as R

    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            s = cosine(centroids.get(a, {}), centroids.get(b, {}))
            if C.RELATION_SIMILARITY <= s < C.NARRATIVE_SIMILARITY:
                add(a, b, R.SIMILAR, s, {"cosine": s})
            ta, tb = narratives[a].topic_id, narratives[b].topic_id
            if ta and ta == tb:
                add(a, b, R.SAME_TOPIC, 0.5, {"topic_id": str(ta)})
            shared = entities[a] & entities[b]
            if shared:
                j = len(shared) / len(entities[a] | entities[b])
                add(a, b, R.SHARES_ENTITY, j, {"entities": sorted(shared)})
            n_shared = shared_counts[(a, b)]
            if n_shared:
                add(a, b, R.SHARES_EVIDENCE, n_shared / max_shared, {"shared_sources": n_shared})
            pair = {statuses.get(a), statuses.get(b)}
            if s >= C.RELATION_SIMILARITY and pair == {
                EvidenceStatus.VERIFIED_TRUE,
                EvidenceStatus.VERIFIED_FALSE,
            }:
                add(a, b, R.CONTRADICTS, s, {"cosine": s})
    session.flush()
    return count
