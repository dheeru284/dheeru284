"""Response recommendation (NARRATIVE_INTELLIGENCE.md §8, rec-v1).

A deterministic decision table over six inputs. There is deliberately no input about who
made a claim, which party it helps, or how persuasive it is.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from app.domain.enums import EvidenceStatus, HarmSeverity, NarrativeStatus, Recommendation
from app.narratives import config as C
from app.narratives.metrics import at_least, level

VERIFIED = (EvidenceStatus.VERIFIED_FALSE, EvidenceStatus.VERIFIED_TRUE)
OPEN_QUESTION = (EvidenceStatus.PENDING_VERIFICATION, EvidenceStatus.UNRESOLVED)


@dataclass(frozen=True)
class RecommendationInputs:
    evidence_status: EvidenceStatus
    public_relevance: float
    momentum: float
    harm_severity: HarmSeverity
    uncertainty: float
    coverage: float


@dataclass(frozen=True)
class RecommendationResult:
    recommendation: Recommendation
    rule: str
    rationale: str
    trace: list[str]
    escalated: bool

    def to_dict(self) -> dict:
        d = asdict(self)
        d["recommendation"] = self.recommendation.value
        return d


def recommend(x: RecommendationInputs) -> RecommendationResult:
    trace = [
        f"evidence_status={x.evidence_status.value}",
        f"public_relevance={x.public_relevance:.2f} ({level(x.public_relevance)})",
        f"momentum={x.momentum:.2f} ({level(x.momentum)})",
        f"harm={x.harm_severity.value}",
        f"uncertainty={x.uncertainty:.2f}",
        f"coverage={x.coverage:.2f}",
    ]
    harm_high = x.harm_severity == HarmSeverity.HIGH
    harm_med = x.harm_severity in (HarmSeverity.MEDIUM, HarmSeverity.HIGH)
    rel_med = at_least(x.public_relevance, "MEDIUM")
    mom_med = at_least(x.momentum, "MEDIUM")

    def done(rec: Recommendation, rule: str, why: str) -> RecommendationResult:
        trace.append(f"{rule}: {why}")
        return RecommendationResult(rec, rule, why, trace, rec == Recommendation.ESCALATE)

    if harm_high and mom_med:
        return done(
            Recommendation.ESCALATE,
            "R1",
            "High potential harm and the narrative is gaining momentum.",
        )
    if harm_high and x.evidence_status not in VERIFIED:
        return done(
            Recommendation.INVESTIGATE,
            "R2",
            "High potential harm and the evidence is not yet verified.",
        )
    if x.evidence_status == EvidenceStatus.VERIFIED_FALSE:
        if x.coverage >= C.HIGH_COVERAGE:
            return done(
                Recommendation.MONITOR,
                "R3",
                "Verified false or misleading, and already well covered by responses.",
            )
        if rel_med or mom_med or harm_med:
            return done(
                Recommendation.CORRECT,
                "R4",
                "Verified false or misleading, relevant or spreading, and not yet "
                "adequately corrected.",
            )
        return done(
            Recommendation.MONITOR,
            "R5",
            "Verified false or misleading but low relevance and momentum.",
        )
    if x.evidence_status == EvidenceStatus.CONTESTED:
        if rel_med or mom_med:
            return done(
                Recommendation.RESPOND,
                "R6",
                "Approved fact-checks point in different directions; publish context.",
            )
        return done(
            Recommendation.INVESTIGATE,
            "R6",
            "Approved fact-checks point in different directions; reconcile them.",
        )
    if x.evidence_status in OPEN_QUESTION:
        if rel_med or mom_med or harm_med or x.uncertainty >= C.MEDIUM:
            return done(
                Recommendation.INVESTIGATE,
                "R7",
                "Not yet verified, and relevant, spreading, potentially harmful or "
                "highly uncertain.",
            )
        return done(Recommendation.MONITOR, "R8", "Not yet verified; low activity so far.")
    if (
        x.evidence_status == EvidenceStatus.VERIFIED_TRUE
        and at_least(x.public_relevance, "HIGH")
        and mom_med
        and x.coverage < C.LOW_COVERAGE
    ):
        return done(
            Recommendation.RESPOND,
            "R9",
            "Verified accurate, in high public demand and not yet addressed.",
        )
    if rel_med or mom_med:
        return done(
            Recommendation.MONITOR,
            "R10",
            "Verified accurate or not checkable, with some public activity.",
        )
    return done(Recommendation.IGNORE, "R11", "No response needed: low relevance and activity.")


def suggest_status(
    result: RecommendationResult,
    x: RecommendationInputs,
    last_seen_at: datetime,
    now: datetime,
) -> NarrativeStatus:
    if (
        x.evidence_status in VERIFIED
        and x.coverage >= C.HIGH_COVERAGE
        and not at_least(x.momentum, "MEDIUM")
    ):
        return NarrativeStatus.RESOLVED
    match result.recommendation:
        case Recommendation.ESCALATE | Recommendation.INVESTIGATE:
            return NarrativeStatus.INVESTIGATE
        case Recommendation.RESPOND:
            return NarrativeStatus.RESPOND
        case Recommendation.CORRECT:
            return NarrativeStatus.CORRECT
        case Recommendation.MONITOR:
            return NarrativeStatus.MONITOR
        case Recommendation.IGNORE:
            idle = now - last_seen_at > timedelta(days=C.ARCHIVE_AFTER_IDLE_DAYS)
            return NarrativeStatus.ARCHIVED if idle else NarrativeStatus.MONITOR
    raise AssertionError(result.recommendation)


# Human-only status transitions (NARRATIVE_INTELLIGENCE.md §11).
S = NarrativeStatus
STATUS_TRANSITIONS: dict[NarrativeStatus, frozenset[NarrativeStatus]] = {
    S.EMERGING: frozenset({S.MONITOR, S.INVESTIGATE, S.RESPOND, S.CORRECT, S.ARCHIVED}),
    S.MONITOR: frozenset({S.INVESTIGATE, S.RESPOND, S.CORRECT, S.RESOLVED, S.ARCHIVED}),
    S.INVESTIGATE: frozenset({S.MONITOR, S.RESPOND, S.CORRECT, S.RESOLVED, S.ARCHIVED}),
    S.RESPOND: frozenset({S.MONITOR, S.CORRECT, S.RESOLVED}),
    S.CORRECT: frozenset({S.MONITOR, S.RESOLVED}),
    S.RESOLVED: frozenset({S.MONITOR, S.ARCHIVED}),
    S.ARCHIVED: frozenset({S.MONITOR}),
}
