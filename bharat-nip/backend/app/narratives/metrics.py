"""Pure metric functions (NARRATIVE_INTELLIGENCE.md §5-§7). No database access."""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.domain.enums import (
    Classification,
    EvidenceStatus,
    HarmSeverity,
    ObservationMetric,
    ResponseType,
)
from app.narratives import config as C

FALSEISH = frozenset(
    {Classification.FALSE, Classification.MISLEADING, Classification.OUT_OF_CONTEXT}
)
TRUEISH = frozenset({Classification.TRUE, Classification.MOSTLY_TRUE})
UNRESOLVED = frozenset({Classification.UNVERIFIED, Classification.INSUFFICIENT_EVIDENCE})
HARM_SCORES = {
    HarmSeverity.NONE: 0.0,
    HarmSeverity.LOW: 0.33,
    HarmSeverity.MEDIUM: 0.66,
    HarmSeverity.HIGH: 1.0,
}


def sat(x: float, k: float) -> float:
    return max(0.0, min(1.0, x / k)) if k > 0 else 0.0


def level(x: float) -> str:
    return "LOW" if x < C.LOW else "MEDIUM" if x < C.MEDIUM else "HIGH"


def at_least(x: float, lvl: str) -> bool:
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    return order[level(x)] >= order[lvl]


# --- velocity, recurrence, momentum ------------------------------------------------------


@dataclass(frozen=True)
class Velocity:
    count_24h: int
    count_7d: int
    count_prev_7d: int
    rate_24h: float
    rate_7d: float
    acceleration: int


def velocity(occurrences: Sequence[datetime], now: datetime) -> Velocity:
    d1, d7, d14 = (now - timedelta(days=n) for n in (1, 7, 14))
    c24 = sum(1 for t in occurrences if d1 < t <= now)
    c7 = sum(1 for t in occurrences if d7 < t <= now)
    p7 = sum(1 for t in occurrences if d14 < t <= d7)
    return Velocity(c24, c7, p7, float(c24), round(c7 / 7, 4), c7 - p7)


def bursts(occurrences: Sequence[datetime], gap_days: int = C.RECURRENCE_GAP_DAYS) -> int:
    ts = sorted(occurrences)
    if not ts:
        return 0
    n = 1
    for prev, cur in itertools.pairwise(ts):
        if (cur - prev) > timedelta(days=gap_days):
            n += 1
    return n


@dataclass(frozen=True)
class ObservationPoint:
    channel: str
    metric: ObservationMetric
    observed_at: datetime
    value: int


def observation_growth(points: Sequence[ObservationPoint], now: datetime) -> float:
    """sum(max(0, latest - value 7+ days earlier)) / max(1, sum(earlier)), per channel+metric."""
    cutoff = now - timedelta(days=7)
    gain, base = 0.0, 0.0
    for key in {(p.channel, p.metric) for p in points}:
        series = sorted(
            (p for p in points if (p.channel, p.metric) == key and p.observed_at <= now),
            key=lambda p: p.observed_at,
        )
        if not series:
            continue
        latest = series[-1].value
        earlier = [p for p in series if p.observed_at <= cutoff]
        if earlier:
            gain += max(0, latest - earlier[-1].value)
            base += earlier[-1].value
    return round(gain / max(1.0, base), 4)


def latest_reach(points: Sequence[ObservationPoint], now: datetime) -> int:
    latest: dict[tuple[str, ObservationMetric], ObservationPoint] = {}
    for p in points:
        if p.observed_at > now:
            continue
        k = (p.channel, p.metric)
        if k not in latest or p.observed_at > latest[k].observed_at:
            latest[k] = p
    return sum(p.value for p in latest.values())


def momentum(v: Velocity, obs_growth: float) -> float:
    return round(
        0.5 * sat(v.rate_7d, 1.0)
        + 0.3 * sat(max(0, v.acceleration), 5)
        + 0.2 * sat(obs_growth, 1.0),
        4,
    )


# --- evidence ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimVerification:
    checkable: bool
    approved_classification: Classification | None  # human-approved final classification
    approved_confidence: float | None


def evidence_status(items: Sequence[ClaimVerification]) -> EvidenceStatus:
    checkable = [i for i in items if i.checkable]
    if not checkable:
        return EvidenceStatus.NOT_CHECKABLE
    finals = {i.approved_classification for i in checkable if i.approved_classification}
    if not finals:
        return EvidenceStatus.PENDING_VERIFICATION
    has_false, has_true = bool(finals & FALSEISH), bool(finals & TRUEISH)
    if has_false and has_true:
        return EvidenceStatus.CONTESTED
    if has_false:
        return EvidenceStatus.VERIFIED_FALSE
    if has_true:
        return EvidenceStatus.VERIFIED_TRUE
    return EvidenceStatus.UNRESOLVED


def evidence_strength(items: Sequence[ClaimVerification], status: EvidenceStatus) -> float:
    if status in (
        EvidenceStatus.PENDING_VERIFICATION,
        EvidenceStatus.UNRESOLVED,
        EvidenceStatus.NOT_CHECKABLE,
    ):
        return 0.0
    checkable = [i for i in items if i.checkable]
    determinative = [
        i
        for i in checkable
        if i.approved_classification and i.approved_classification not in UNRESOLVED
    ]
    if not determinative:
        return 0.0
    mean_conf = sum(i.approved_confidence or 0.0 for i in determinative) / len(determinative)
    approved = sum(1 for i in checkable if i.approved_classification)
    return round(mean_conf * approved / len(checkable), 4)


# --- public interest, harm, uncertainty, coverage ----------------------------------------


@dataclass(frozen=True)
class InterestIndicators:
    distinct_submissions: int
    distinct_origins: int
    channels: int
    reach: int

    def score(self) -> float:
        return round(
            0.3 * sat(self.distinct_origins, 5)
            + 0.2 * sat(self.distinct_submissions, 10)
            + 0.2 * sat(self.channels, 4)
            + 0.3 * min(1.0, math.log10(1 + self.reach) / 6),
            4,
        )


def harm_score(severity: HarmSeverity) -> float | None:
    return HARM_SCORES.get(severity)  # None = UNASSESSED (unknown)


def uncertainty(
    items: Sequence[ClaimVerification], status: EvidenceStatus, severity: HarmSeverity
) -> float:
    checkable = [i for i in items if i.checkable]
    if checkable:
        unverified = sum(
            1
            for i in checkable
            if not i.approved_classification or i.approved_classification in UNRESOLVED
        ) / len(checkable)
    else:
        unverified = 0.0
    conflict = 1.0 if status == EvidenceStatus.CONTESTED else 0.0
    harm_unknown = 1.0 if severity == HarmSeverity.UNASSESSED else 0.0
    return round(0.6 * unverified + 0.25 * conflict + 0.15 * harm_unknown, 4)


@dataclass(frozen=True)
class ResponseRecord:
    response_type: ResponseType
    published_at: datetime


@dataclass
class Coverage:
    score: float
    stale: bool
    components: dict[str, float] = field(default_factory=dict)


def coverage(
    responses: Sequence[ResponseRecord],
    external_fact_check_evidence: bool,
    occurrences: Iterable[datetime],
) -> Coverage:
    types = {r.response_type for r in responses}
    comp = {
        "own_response": 0.6
        if types & {ResponseType.FACT_CHECK, ResponseType.CORRECTION, ResponseType.CLARIFICATION}
        else 0.0,
        "external_fact_check": 0.3
        if ResponseType.EXTERNAL_FACT_CHECK in types or external_fact_check_evidence
        else 0.0,
        "context_note": 0.1 if ResponseType.CONTEXT_NOTE in types else 0.0,
    }
    score = min(1.0, sum(comp.values()))
    stale = False
    if responses:
        latest = max(r.published_at for r in responses)
        after = sum(1 for t in occurrences if t > latest)
        if after >= C.STALE_RESPONSE_OCCURRENCES:
            stale = True
            score /= 2
    return Coverage(round(score, 4), stale, comp)


def harm_signals(texts: Iterable[str]) -> list[dict[str, str]]:
    """Keyword hits that should prompt a harm assessment. Never sets severity."""
    blob = " ".join(texts).lower()
    hits = []
    for category, words in C.HARM_SIGNAL_LEXICON.items():
        found = sorted({w for w in words if w in blob})
        if found:
            hits.append({"category": category, "keywords": ", ".join(found)})
    return hits


def emerging(recent: int, baseline_weekly: float) -> bool:
    return recent >= C.EMERGING_MIN_RECENT and recent >= 2 * baseline_weekly + 1
