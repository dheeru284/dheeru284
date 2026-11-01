"""Unit tests for the pure narrative modules: similarity, metrics, recommendation table."""

import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.domain.enums import (
    Classification,
    EvidenceStatus,
    HarmSeverity,
    NarrativeStatus,
    ObservationMetric,
    Recommendation,
    ResponseType,
)
from app.narratives import metrics as M
from app.narratives import recommend as R
from app.narratives.similarity import (
    TfidfSimilarity,
    centroid,
    cosine,
    greedy_cluster,
    label_terms,
    top_terms,
)

NOW = datetime(2026, 6, 30, 12, tzinfo=UTC)
ES = EvidenceStatus


# --- similarity -------------------------------------------------------------------------


def test_tfidf_paraphrases_close_unrelated_far_and_speaker_ignored():
    s = TfidfSimilarity()
    s.fit(
        {
            "a": "[SPEAKER] said the Riverland river bridge collapsed in March",
            "b": "Riverland river bridge collapsed in March after opening",
            "c": "Riverland tea exports doubled in the last decade",
        }
    )
    assert cosine(s.vector("a"), s.vector("b")) > 0.45
    assert cosine(s.vector("a"), s.vector("c")) < 0.1
    assert "speaker" not in s.vector("a")


def test_greedy_cluster_is_deterministic_and_centroid_normalized():
    s = TfidfSimilarity()
    docs = {"1": "bridge collapsed march", "2": "bridge collapsed in march", "3": "tea exports"}
    s.fit(docs)
    vec = {k: s.vector(k) for k in docs}
    assert greedy_cluster(["1", "2", "3"], vec, 0.45) == [["1", "2"], ["3"]]
    c = centroid(vec[k] for k in ["1", "2"])
    assert sum(x * x for x in c.values()) == pytest.approx(1.0)
    assert set(top_terms(c, 2)) <= {"bridge", "collapsed", "march"}


# --- metrics ----------------------------------------------------------------------------


def test_velocity_and_bursts():
    occ = [NOW - timedelta(days=d) for d in (40, 38, 10, 3, 1, 0.5)]
    v = M.velocity(occ, NOW)
    assert (v.count_24h, v.count_7d, v.count_prev_7d) == (1, 3, 1)
    assert v.rate_7d == pytest.approx(3 / 7, abs=1e-4)
    assert v.acceleration == 2
    assert M.bursts(occ) == 2  # 40/38 and 10/3/1/0.5 (gaps <= 7 days)
    assert M.bursts([]) == 0


def test_observation_growth_reach_and_momentum():
    P = M.ObservationPoint
    pts = [
        P("video", ObservationMetric.VIEWS, NOW - timedelta(days=10), 1000),
        P("video", ObservationMetric.VIEWS, NOW - timedelta(days=1), 3000),
        P("news", ObservationMetric.ARTICLES, NOW - timedelta(days=1), 4),
    ]
    assert M.observation_growth(pts, NOW) == pytest.approx(2.0)
    assert M.latest_reach(pts, NOW) == 3004
    v = M.velocity([NOW - timedelta(hours=h) for h in range(7)], NOW)
    assert M.momentum(v, 2.0) == pytest.approx(0.5 + 0.3 + 0.2)
    assert M.level(0.2) == "LOW" and M.level(0.5) == "MEDIUM" and M.level(0.7) == "HIGH"


def V(cls=None, conf=None, checkable=True):
    return M.ClaimVerification(checkable, cls, conf)


@pytest.mark.parametrize(
    ("items", "expected"),
    [
        ([V(checkable=False)], ES.NOT_CHECKABLE),
        ([V(), V()], ES.PENDING_VERIFICATION),
        ([V(Classification.FALSE, 0.9), V()], ES.VERIFIED_FALSE),
        ([V(Classification.MISLEADING, 0.7)], ES.VERIFIED_FALSE),
        ([V(Classification.TRUE, 0.8)], ES.VERIFIED_TRUE),
        ([V(Classification.TRUE, 0.8), V(Classification.FALSE, 0.8)], ES.CONTESTED),
        ([V(Classification.UNVERIFIED, 0.3)], ES.UNRESOLVED),
    ],
)
def test_evidence_status(items, expected):
    assert M.evidence_status(items) == expected


def test_evidence_strength_and_uncertainty():
    items = [V(Classification.FALSE, 0.9), V(Classification.FALSE, 0.7), V(), V()]
    st = M.evidence_status(items)
    assert M.evidence_strength(items, st) == pytest.approx(0.8 * 2 / 4)
    assert M.uncertainty(items, st, HarmSeverity.UNASSESSED) == pytest.approx(0.6 * 0.5 + 0.15)
    assert M.evidence_strength([V()], ES.PENDING_VERIFICATION) == 0.0


def test_public_interest_scoring():
    low = M.InterestIndicators(1, 1, 0, 0).score()
    high = M.InterestIndicators(10, 5, 4, 1_000_000).score()
    assert low < 0.1 and high == pytest.approx(1.0)


def test_coverage_and_staleness():
    RR = M.ResponseRecord
    t = NOW - timedelta(days=5)
    cov = M.coverage([RR(ResponseType.FACT_CHECK, t)], False, [NOW - timedelta(days=6)])
    assert cov.score == pytest.approx(0.6) and not cov.stale
    full = M.coverage([RR(ResponseType.CORRECTION, t), RR(ResponseType.CONTEXT_NOTE, t)], True, [])
    assert full.score == pytest.approx(1.0)
    stale = M.coverage(
        [RR(ResponseType.FACT_CHECK, t)], False, [NOW - timedelta(days=d) for d in (1, 2, 3)]
    )
    assert stale.stale and stale.score == pytest.approx(0.3)


def test_harm_signals_are_suggestions_by_category():
    hits = M.harm_signals(["Polling booth hours changed", "new vaccine causes illness"])
    assert {h["category"] for h in hits} == {"ELECTORAL_PROCESS", "PUBLIC_HEALTH"}
    assert M.harm_signals(["literacy rose"]) == []


def test_emerging_rule():
    assert M.emerging(3, 0.0) and M.emerging(5, 2.0)
    assert not M.emerging(2, 0.0) and not M.emerging(4, 2.0)


# --- recommendation decision table ------------------------------------------------------


def X(status, rel=0.1, mom=0.1, harm=HarmSeverity.NONE, unc=0.1, cov=0.0):
    return R.RecommendationInputs(status, rel, mom, harm, unc, cov)


@pytest.mark.parametrize(
    ("inputs", "rec", "rule"),
    [
        (X(ES.VERIFIED_TRUE, mom=0.7, harm=HarmSeverity.HIGH), "ESCALATE", "R1"),
        (X(ES.PENDING_VERIFICATION, harm=HarmSeverity.HIGH), "INVESTIGATE", "R2"),
        (X(ES.VERIFIED_FALSE, rel=0.9, cov=0.8), "MONITOR", "R3"),
        (X(ES.VERIFIED_FALSE, rel=0.5), "CORRECT", "R4"),
        (X(ES.VERIFIED_FALSE, harm=HarmSeverity.MEDIUM), "CORRECT", "R4"),
        (X(ES.VERIFIED_FALSE), "MONITOR", "R5"),
        (X(ES.CONTESTED, rel=0.5), "RESPOND", "R6"),
        (X(ES.CONTESTED), "INVESTIGATE", "R6"),
        (X(ES.PENDING_VERIFICATION, mom=0.5), "INVESTIGATE", "R7"),
        (X(ES.UNRESOLVED, unc=0.7), "INVESTIGATE", "R7"),
        (X(ES.PENDING_VERIFICATION), "MONITOR", "R8"),
        (X(ES.VERIFIED_TRUE, rel=0.8, mom=0.5, cov=0.1), "RESPOND", "R9"),
        (X(ES.VERIFIED_TRUE, rel=0.5), "MONITOR", "R10"),
        (X(ES.NOT_CHECKABLE, mom=0.5), "MONITOR", "R10"),
        (X(ES.VERIFIED_TRUE), "IGNORE", "R11"),
        (X(ES.NOT_CHECKABLE), "IGNORE", "R11"),
    ],
)
def test_decision_table(inputs, rec, rule):
    result = R.recommend(inputs)
    assert (result.recommendation.value, result.rule) == (rec, rule)
    assert result.trace[-1].startswith(rule)


def test_every_recommendation_is_reachable():
    seen = {
        R.recommend(X(*args)).recommendation
        for args in [
            (ES.VERIFIED_TRUE, 0.1, 0.7, HarmSeverity.HIGH),
            (ES.VERIFIED_FALSE, 0.5),
            (ES.CONTESTED, 0.5),
            (ES.PENDING_VERIFICATION, 0.5),
            (ES.PENDING_VERIFICATION,),
            (ES.VERIFIED_TRUE,),
        ]
    }
    assert seen == set(Recommendation)


def test_unassessed_harm_is_never_treated_as_high():
    r = R.recommend(X(ES.VERIFIED_TRUE, mom=0.9, harm=HarmSeverity.UNASSESSED))
    assert r.recommendation != Recommendation.ESCALATE


def test_suggested_status():
    rec = R.recommend(X(ES.VERIFIED_FALSE, cov=0.9))
    assert R.suggest_status(rec, X(ES.VERIFIED_FALSE, cov=0.9), NOW, NOW) == (
        NarrativeStatus.RESOLVED
    )
    ignore = R.recommend(X(ES.VERIFIED_TRUE))
    assert R.suggest_status(ignore, X(ES.VERIFIED_TRUE), NOW - timedelta(days=40), NOW) == (
        NarrativeStatus.ARCHIVED
    )
    assert R.suggest_status(ignore, X(ES.VERIFIED_TRUE), NOW - timedelta(days=2), NOW) == (
        NarrativeStatus.MONITOR
    )
    esc = R.recommend(X(ES.PENDING_VERIFICATION, mom=0.9, harm=HarmSeverity.HIGH))
    assert R.suggest_status(esc, X(ES.PENDING_VERIFICATION), NOW, NOW) == (
        NarrativeStatus.INVESTIGATE
    )


def test_status_transitions_cover_every_status_and_allow_reopening():
    assert set(R.STATUS_TRANSITIONS) == set(NarrativeStatus)
    assert NarrativeStatus.EMERGING not in set().union(*R.STATUS_TRANSITIONS.values())
    assert NarrativeStatus.MONITOR in R.STATUS_TRANSITIONS[NarrativeStatus.ARCHIVED]
    assert NarrativeStatus.MONITOR in R.STATUS_TRANSITIONS[NarrativeStatus.RESOLVED]


def test_recommendation_has_no_speaker_party_or_persuasion_inputs():
    fields = set(R.RecommendationInputs.__dataclass_fields__)
    assert fields == {
        "evidence_status",
        "public_relevance",
        "momentum",
        "harm_severity",
        "uncertainty",
        "coverage",
    }


def test_narrative_code_never_reads_speaker_identity():
    """The narrative package must not touch speaker attribution or speaker entities."""
    pkg = Path(inspect.getfile(R)).parent
    for path in pkg.glob("*.py"):
        source = path.read_text()
        assert "speaker_entity_id" not in source, path.name
        assert "persuasion" not in source.lower(), path.name


def test_topic_labels_prefer_words_over_numbers():
    v = {"2023": 0.9, "81": 0.8, "literacy": 0.5, "rate": 0.4}
    assert label_terms(v, 3) == ["literacy", "rate", "2023"]
