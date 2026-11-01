"""Evidence ranking (FR-5): a deterministic, versioned score from seven factors.

score = sum(weight_i * factor_i), every factor in [0, 1]. All components are stored with
the ranking so that a reviewer can see exactly why an item ranked where it did.
Changing any number here requires a new RANKING_VERSION.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.domain.enums import ActorType, AuthorityLevel, Directness, SourceType, Stance
from app.models import Claim, Evidence, EvidenceRanking, RegistrySource, Source
from app.services.registry import effective_authority, normalize_domain

RANKING_VERSION = "rank-v2"

WEIGHTS = {
    "authority": 0.20,
    "primary_source": 0.15,
    "relevance": 0.20,
    "recency": 0.10,
    "directness": 0.15,
    "corroboration": 0.10,
    "document_quality": 0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

AUTHORITY_SCORES = {
    AuthorityLevel.PRIMARY_AUTHORITY: 1.0,
    AuthorityLevel.ESTABLISHED: 0.8,
    AuthorityLevel.GENERAL: 0.55,
    AuthorityLevel.UNASSESSED: 0.4,
    AuthorityLevel.LIMITED: 0.25,
}
RECENCY_HALF_LIFE_YEARS = 3.0
OUTDATED_AFTER_YEARS = 5.0


@dataclass(frozen=True)
class RankedEvidence:
    evidence: Evidence
    source: Source
    score: float
    components: dict


def origin_key(source: Source) -> str:
    """Identifies an independent origin, for corroboration and single-source checks."""
    if source.registry_source_id:
        return f"registry:{source.registry_source_id}"
    domain = normalize_domain(source.url)
    if domain:
        return f"domain:{domain}"
    return f"publisher:{(source.publisher_name or source.id).__str__().lower()}"


def reference_date(claim: Claim, fallback: datetime | None = None) -> date:
    """The date the claim is about (or when it was made), for recency."""
    if claim.claim_date:
        return claim.claim_date
    if claim.statement_date:
        return claim.statement_date
    if claim.time_reference and claim.time_reference.strip()[:4].isdigit():
        year = int(claim.time_reference.strip()[:4])
        if 1800 < year < 2200:
            return date(year, 12, 31)
    return (fallback or datetime.now(UTC)).date()


def evidence_age_years(source: Source, ref: date) -> float | None:
    if source.published_at is None:
        return None
    return (ref - source.published_at.date()).days / 365.25


def recency_score(source: Source, ref: date) -> tuple[float, str]:
    age = evidence_age_years(source, ref)
    if age is None:
        return 0.5, "publication date unknown"
    if age <= 0:
        return 1.0, "published on/after the period the claim refers to"
    return round(0.5 ** (age / RECENCY_HALF_LIFE_YEARS), 4), f"{age:.1f} years before reference"


def document_quality(source: Source) -> tuple[float, dict]:
    signals = {
        "has_title": bool(source.title and source.title != "(untitled)"),
        "identifiable_publisher": bool(source.publisher_name or source.registry_source_id),
        "has_publication_date": source.published_at is not None,
        "substantive_length": len(source.content_text) >= 500,
        "secure_or_ingested": (source.url or "").startswith("https://")
        or source.ingested_by_id is not None,
        "not_social_media": source.source_type != SourceType.SOCIAL_MEDIA_POST,
    }
    return round(sum(signals.values()) / len(signals), 4), signals


def rank_claim_evidence(session: Session, claim: Claim) -> list[RankedEvidence]:
    rows = session.execute(
        select(Evidence, Source)
        .join(Source, Source.id == Evidence.source_id)
        .where(Evidence.claim_id == claim.id)
    ).all()
    registry = {
        r.id: r
        for r in session.scalars(
            select(RegistrySource).where(
                RegistrySource.id.in_(
                    {s.registry_source_id for _, s in rows if s.registry_source_id}
                )
            )
        )
    }
    ref = reference_date(claim)
    origins_by_stance: dict[Stance, set[str]] = {}
    for ev, src in rows:
        origins_by_stance.setdefault(ev.stance, set()).add(origin_key(src))

    ranked: list[RankedEvidence] = []
    for ev, src in rows:
        auth = effective_authority(registry.get(src.registry_source_id), claim.normalized_text)
        recency, recency_basis = recency_score(src, ref)
        quality, quality_signals = document_quality(src)
        others = origins_by_stance.get(ev.stance, set()) - {origin_key(src)}
        factors = {
            "authority": AUTHORITY_SCORES[auth.level],
            "primary_source": 1.0 if src.is_primary else 0.4,
            "relevance": ev.relevance,
            "recency": recency,
            "directness": 1.0 if ev.directness == Directness.DIRECT else 0.5,
            "corroboration": min(1.0, len(others) / 2),
            "document_quality": quality,
        }
        score = round(sum(WEIGHTS[k] * v for k, v in factors.items()), 4)
        components = {
            "factors": factors,
            "weights": WEIGHTS,
            "authority_level": auth.level.value,
            "authority_basis": auth.basis,
            "recency_basis": recency_basis,
            "reference_date": ref.isoformat(),
            "independent_corroborating_origins": len(others),
            "quality_signals": quality_signals,
            "origin": origin_key(src),
        }
        ranked.append(RankedEvidence(ev, src, score, components))

    ranked.sort(key=lambda r: (-r.score, str(r.evidence.id)))
    return ranked


def persist_rankings(session: Session, claim: Claim) -> list[RankedEvidence]:
    ranked = rank_claim_evidence(session, claim)
    existing = {
        r.evidence_id: r
        for r in session.scalars(
            select(EvidenceRanking).where(
                EvidenceRanking.evidence_id.in_([r.evidence.id for r in ranked]),
                EvidenceRanking.ranking_version == RANKING_VERSION,
            )
        )
    }
    for r in ranked:
        row = existing.get(r.evidence.id)
        if row is None:
            session.add(
                EvidenceRanking(
                    evidence_id=r.evidence.id,
                    ranking_version=RANKING_VERSION,
                    score=r.score,
                    components=r.components,
                )
            )
        else:  # re-ranked after more research (corroboration can change)
            row.score = r.score
            row.components = r.components
    session.flush()
    AuditService(session).record(
        actor_type=ActorType.SYSTEM,
        actor_id="system:ranking",
        action="evidence.ranked",
        entity_type="claim",
        entity_id=claim.id,
        payload={
            "ranking_version": RANKING_VERSION,
            "ranking": [{"evidence_id": str(r.evidence.id), "score": r.score} for r in ranked],
        },
    )
    return ranked
