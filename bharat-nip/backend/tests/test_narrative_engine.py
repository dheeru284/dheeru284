"""Narrative engine integration tests against the real database (all data fictional)."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.domain.enums import (
    Classification,
    EvidenceStatus,
    HarmCategory,
    HarmSeverity,
    MembershipSource,
    NarrativeStatus,
    ObservationMetric,
    Recommendation,
    RelationType,
    ResponseType,
    UserRole,
)
from app.models import (
    AuditEvent,
    Claim,
    Narrative,
    NarrativeClaim,
    NarrativeMetric,
    NarrativeRelation,
    Topic,
)
from app.narratives import config as C
from app.narratives import service
from app.narratives.engine import run_engine
from app.narratives.queries import (
    claim_history,
    evidence_timeline,
    graph,
    history_matches,
    latest_metrics,
)
from app.services.errors import Conflict, Unprocessable
from tests.factories import make_user
from tests.narrative_factory import (
    BRIDGE,
    LITERACY,
    NOW,
    POLLING,
    UNRELATED,
    approve,
    days_ago,
    make_claim,
)


@pytest.fixture
def people(db_session):
    return {
        "analyst": make_user(db_session, UserRole.ANALYST),
        "reviewer": make_user(db_session, UserRole.REVIEWER),
    }


def bridge_story(db_session, analyst):
    """Bridge claims in two bursts five weeks apart, from four different origins."""
    times = [days_ago(40), days_ago(38), days_ago(3), days_ago(1)]
    return [
        make_claim(db_session, analyst, text, seen_at=t, origin_url=f"https://site{i}.example/a")
        for i, (text, t) in enumerate(zip(BRIDGE, times, strict=True))
    ]


def narrative_for(db_session, claim) -> Narrative:
    nid = db_session.scalar(
        select(NarrativeClaim.narrative_id).where(NarrativeClaim.claim_id == claim.id)
    )
    return db_session.get(Narrative, nid) if nid else None


def test_detection_velocity_recurrence_and_idempotency(db_session, people):
    a = people["analyst"]
    bridge = bridge_story(db_session, a)
    lit = [make_claim(db_session, a, t, seen_at=days_ago(20 + i)) for i, t in enumerate(LITERACY)]
    lone = make_claim(db_session, a, UNRELATED, seen_at=days_ago(2))

    report = run_engine(db_session, NOW)
    assert len(report.narratives_created) == 2
    nb, nl = narrative_for(db_session, bridge[0]), narrative_for(db_session, lit[0])
    assert nb and nl and nb.id != nl.id
    assert {narrative_for(db_session, c).id for c in bridge} == {nb.id}
    assert narrative_for(db_session, lone) is None  # a single claim is not a narrative
    assert nb.status == NarrativeStatus.EMERGING
    assert "[SPEAKER]" not in nb.title and "said" not in nb.title.lower()

    m = latest_metrics(db_session, nb.id)
    assert m.claim_count == 4
    assert m.recurring is True and m.details["bursts"] == 2
    assert m.details["velocity"]["count_7d"] == 2
    assert m.rate_7d == pytest.approx(2 / 7, abs=1e-3)
    assert m.acceleration == 2
    assert m.evidence_status == EvidenceStatus.PENDING_VERIFICATION
    assert m.details["public_interest_indicators"]["distinct_origins"] == 4

    # Re-running on the same data at the same instant changes nothing.
    snapshots = db_session.scalar(select(func.count()).select_from(NarrativeMetric))
    again = run_engine(db_session, NOW)
    assert again.narratives_created == [] and again.snapshots_written == 0
    assert db_session.scalar(select(func.count()).select_from(NarrativeMetric)) == snapshots
    assert (
        db_session.scalar(select(func.count()).where(AuditEvent.action == "narrative.created")) == 2
    )


def test_new_claim_joins_existing_narrative(db_session, people):
    a = people["analyst"]
    bridge = bridge_story(db_session, a)
    run_engine(db_session, NOW)
    late = make_claim(
        db_session,
        a,
        "Riverland river bridge collapsed in March, residents say",
        seen_at=NOW - timedelta(hours=2),
    )
    report = run_engine(db_session, NOW)
    assert report.claims_assigned == 1
    assert narrative_for(db_session, late).id == narrative_for(db_session, bridge[0]).id
    assert (
        db_session.scalar(select(func.count()).where(AuditEvent.action == "narrative.claim_added"))
        == 1
    )


def test_evidence_status_drives_recommendation(db_session, people):
    a, r = people["analyst"], people["reviewer"]
    bridge = bridge_story(db_session, a)
    run_engine(db_session, NOW)
    nb = narrative_for(db_session, bridge[0])
    assert latest_metrics(db_session, nb.id).recommendation == Recommendation.INVESTIGATE  # R7

    approve(db_session, bridge[0], r, Classification.FALSE, 0.9)
    run_engine(db_session, NOW)
    m = latest_metrics(db_session, nb.id)
    assert m.evidence_status == EvidenceStatus.VERIFIED_FALSE
    assert m.evidence_strength == pytest.approx(0.9 * 1 / 4)
    assert m.recommendation == Recommendation.MONITOR  # R5: low relevance and momentum

    # Aggregate public counts raise relevance: verified false + relevant => CORRECT.
    service.add_observation(
        db_session,
        a,
        nb.id,
        observed_at=days_ago(1),
        channel="video-site",
        metric=ObservationMetric.VIEWS,
        value=50_000,
        source_url=None,
        note=None,
    )
    run_engine(db_session, NOW)
    m = latest_metrics(db_session, nb.id)
    assert m.recommendation == Recommendation.CORRECT
    assert m.details["recommendation"]["rule"] == "R4"

    # Once a correction exists, the recommendation steps down and RESOLVED is suggested.
    service.add_response(
        db_session,
        a,
        nb.id,
        response_type=ResponseType.FACT_CHECK,
        title="Fact-check",
        url=None,
        channel=None,
        published_at=NOW,
    )
    service.add_response(
        db_session,
        a,
        nb.id,
        response_type=ResponseType.EXTERNAL_FACT_CHECK,
        title="External",
        url=None,
        channel=None,
        published_at=NOW,
    )
    run_engine(db_session, NOW)
    m = latest_metrics(db_session, nb.id)
    assert m.coverage == pytest.approx(0.9)
    assert (
        m.recommendation == Recommendation.MONITOR and m.details["recommendation"]["rule"] == "R3"
    )
    assert m.suggested_status == NarrativeStatus.RESOLVED
    changes = db_session.scalars(
        select(AuditEvent.payload).where(AuditEvent.action == "narrative.recommendation_changed")
    ).all()
    assert [c["to"] for c in changes] == ["INVESTIGATE", "MONITOR", "CORRECT", "MONITOR"]


def test_contested_and_escalation(db_session, people):
    a, r = people["analyst"], people["reviewer"]
    bridge = bridge_story(db_session, a)
    approve(db_session, bridge[0], r, Classification.FALSE)
    approve(db_session, bridge[1], r, Classification.TRUE)
    run_engine(db_session, NOW)
    nb = narrative_for(db_session, bridge[0])
    m = latest_metrics(db_session, nb.id)
    assert m.evidence_status == EvidenceStatus.CONTESTED
    assert m.uncertainty >= 0.25

    service.assess_harm(
        db_session,
        a,
        nb.id,
        HarmCategory.PUBLIC_SAFETY,
        HarmSeverity.HIGH,
        "Could lead people to avoid a safe route or panic.",
    )
    for i in range(6):  # a burst of new occurrences => momentum MEDIUM+
        make_claim(db_session, a, BRIDGE[i % 4], seen_at=NOW - timedelta(hours=i + 1))
    run_engine(db_session, NOW)
    m = latest_metrics(db_session, nb.id)
    assert m.recommendation == Recommendation.ESCALATE
    assert m.suggested_status == NarrativeStatus.INVESTIGATE
    assert m.details["recommendation"]["escalated"] is True


def test_emerging_topic_and_harm_signals(db_session, people):
    a = people["analyst"]
    polling = [make_claim(db_session, a, POLLING[i % 2], seen_at=days_ago(i + 1)) for i in range(3)]
    run_engine(db_session, NOW)
    topic = db_session.get(
        Topic, db_session.get(Narrative, narrative_for(db_session, polling[0]).id).topic_id
    )
    assert topic.is_emerging and topic.recent_count == 3 and topic.emerging_since == NOW
    m = latest_metrics(db_session, narrative_for(db_session, polling[0]).id)
    categories = {s["category"] for s in m.details["harm"]["signals"]}
    assert "ELECTORAL_PROCESS" in categories
    # Signals never set severity: it stays unassessed until an analyst decides.
    assert m.details["harm"]["severity"] == "UNASSESSED" and m.harm_score is None


def test_relations_use_subject_entities_and_contradictions(db_session, people, monkeypatch):
    a, r = people["analyst"], people["reviewer"]
    monkeypatch.setattr(C, "NARRATIVE_SIMILARITY", 0.9)  # keep two related stories apart
    pwd = {
        "name": "Riverland Public Works Department",
        "type": "GOVERNMENT_BODY",
        "role": "SUBJECT",
    }
    speaker = {"name": "A Fictional Leader", "type": "PERSON", "role": "SPEAKER"}
    collapsed = "Riverland Public Works Department says the river bridge collapsed in March"
    opened = "Riverland Public Works Department says the river bridge opened in March"
    n1 = [
        make_claim(db_session, a, collapsed, seen_at=days_ago(5 + i), entities=[pwd, speaker])
        for i in range(2)
    ]
    n2 = [
        make_claim(db_session, a, opened, seen_at=days_ago(5 + i), entities=[pwd, speaker])
        for i in range(2)
    ]
    approve(db_session, n1[0], r, Classification.FALSE)
    approve(db_session, n2[0], r, Classification.TRUE)
    run_engine(db_session, NOW)
    types = {rel.relation_type for rel in db_session.scalars(select(NarrativeRelation))}
    assert {RelationType.SIMILAR, RelationType.SHARES_ENTITY, RelationType.CONTRADICTS} <= types
    shared = db_session.scalar(
        select(NarrativeRelation).where(
            NarrativeRelation.relation_type == RelationType.SHARES_ENTITY
        )
    )
    # The shared SPEAKER never creates an edge; only the subject entity does.
    assert shared.details["entities"] == ["riverland public works department"]


def test_speaker_identity_does_not_change_any_metric(db_session, people):
    """Swap every claim's speaker (person and party) and re-run at the same instant:
    no snapshot may change. The engine has no speaker input."""
    a = people["analyst"]
    claims = bridge_story(db_session, a)
    for c in claims:
        c.entities = [{"name": "Leader of Party A", "type": "PERSON", "role": "SPEAKER"}]
    run_engine(db_session, NOW)
    before = db_session.scalar(select(func.count()).select_from(NarrativeMetric))
    for c in claims:
        c.entities = [{"name": "Leader of Party B", "type": "PERSON", "role": "SPEAKER"}]
    db_session.flush()
    report = run_engine(db_session, NOW)
    assert report.snapshots_written == 0
    assert db_session.scalar(select(func.count()).select_from(NarrativeMetric)) == before


def test_manual_operations_status_harm_and_exclusion(db_session, people):
    a = people["analyst"]
    bridge = bridge_story(db_session, a)
    run_engine(db_session, NOW)
    nb = narrative_for(db_session, bridge[0])

    service.remove_claim(db_session, a, nb.id, bridge[3].id, "Different bridge, per analyst.")
    run_engine(db_session, NOW)
    row = db_session.scalar(select(NarrativeClaim).where(NarrativeClaim.claim_id == bridge[3].id))
    assert row.excluded and row.narrative_id == nb.id  # the engine did not re-add it
    assert latest_metrics(db_session, nb.id).claim_count == 3

    with pytest.raises(Unprocessable):
        service.remove_claim(db_session, a, nb.id, bridge[2].id, " ")
    with pytest.raises(Unprocessable):
        service.set_status(db_session, a, nb.id, NarrativeStatus.MONITOR, "")
    with pytest.raises(Conflict):
        service.set_status(db_session, a, nb.id, NarrativeStatus.RESOLVED, "too early")
    service.set_status(db_session, a, nb.id, NarrativeStatus.MONITOR, "Tracking.")
    service.set_status(db_session, a, nb.id, NarrativeStatus.RESOLVED, "Corrected.", at=NOW)
    with pytest.raises(Unprocessable):
        service.assess_harm(
            db_session, a, nb.id, HarmCategory.PUBLIC_SAFETY, HarmSeverity.MEDIUM, None
        )
    with pytest.raises(Unprocessable):
        service.assess_harm(db_session, a, nb.id, HarmCategory.NONE, HarmSeverity.LOW, "x")

    # New activity after RESOLVED is flagged, but the status itself does not change.
    make_claim(db_session, a, BRIDGE[0], seen_at=NOW + timedelta(minutes=5))
    run_engine(db_session, NOW + timedelta(hours=1))
    db_session.refresh(nb)
    assert nb.status == NarrativeStatus.RESOLVED
    assert latest_metrics(db_session, nb.id).details["reactivated"] is True

    lit = [make_claim(db_session, a, t, seen_at=days_ago(9)) for t in LITERACY]
    manual = service.create_manual(db_session, a, [lit[0].id], "Literacy claims", None)
    assert manual.origin.value == "MANUAL"
    with pytest.raises(Conflict):
        service.create_manual(db_session, a, [lit[0].id], None, None)
    run_engine(db_session, NOW + timedelta(hours=1))
    # The engine assigns the matching claim to the analyst's narrative.
    assert narrative_for(db_session, lit[1]).id == manual.id
    sources = {
        m.added_by
        for m in db_session.scalars(
            select(NarrativeClaim).where(NarrativeClaim.narrative_id == manual.id)
        )
    }
    assert sources == {MembershipSource.USER, MembershipSource.ENGINE}


def test_history_matching_claim_history_timeline_and_graph(db_session, people):
    a, r = people["analyst"], people["reviewer"]
    bridge = bridge_story(db_session, a)
    approve(db_session, bridge[0], r, Classification.FALSE, decided_at=days_ago(37))
    other = make_claim(db_session, a, UNRELATED, seen_at=days_ago(30))
    run_engine(db_session, NOW)

    matches = history_matches(db_session, bridge[3].id)
    ids = [m["claim_id"] for m in matches]
    assert str(bridge[0].id) in ids and str(other.id) not in ids
    first = next(m for m in matches if m["claim_id"] == str(bridge[0].id))
    assert first["approved_classification"] == "FALSE" and first["narrative_id"]
    assert history_matches(db_session, bridge[0].id) == []  # nothing earlier

    nb = narrative_for(db_session, bridge[0])
    history = claim_history(db_session, nb.id)
    assert [h["burst"] for h in history] == [1, 1, 2, 2]
    assert history[0]["approved_classification"] == "FALSE"
    assert all("SPEAKER" not in h["text"] for h in history)

    timeline = evidence_timeline(db_session, nb.id)
    assert [e["kind"] for e in timeline] == ["REVIEW_DECISION"]

    g = graph(db_session)
    assert [n["id"] for n in g["nodes"]] == [str(nb.id)]
    assert g["nodes"][0]["recommendation"] is not None


def test_engine_run_is_audited(db_session, people):
    bridge_story(db_session, people["analyst"])
    run_engine(db_session, NOW)
    run = db_session.scalar(select(AuditEvent).where(AuditEvent.action == "narrative_engine.run"))
    assert run.payload["claims"] == 4 and len(run.payload["narratives_created"]) == 1
    assert db_session.scalar(select(func.count()).where(AuditEvent.action == "topic.created")) >= 1


def test_narrative_schema_holds_no_personal_or_political_profiling_fields():
    """Guard: narrative tables must stay aggregate. No columns about individual people,
    accounts, ideology or persuasion may be added."""
    from app.db.base import Base

    forbidden = (
        "voter",
        "person",
        "account",
        "handle",
        "follower",
        "ideology",
        "party",
        "persuasion",
        "psych",
        "demographic",
        "age",
        "gender",
        "religion",
        "caste",
    )
    tables = [
        t for name, t in Base.metadata.tables.items() if name.startswith(("narrative", "topic"))
    ]
    assert len(tables) == 8
    for table in tables:
        for column in table.columns:
            name = column.name.lower()
            assert not any(word in name.split("_") for word in forbidden), f"{table}.{name}"
    _ = Claim  # claims keep only public speaker attribution, unchanged by Phase 2
