import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from app.domain.enums import (
    AuthorityLevel,
    Classification,
    Directness,
    RegistryVerificationStatus,
    SourceType,
    Stance,
)
from app.models import RegistrySource
from app.services.assessment import calibrate
from app.services.ranking import WEIGHTS, document_quality, recency_score
from app.services.registry import effective_authority, normalize_domain


def src(**kw):
    base = {
        "id": uuid.uuid4(),
        "registry_source_id": None,
        "url": "https://example.org/a",
        "publisher_name": "Example",
        "published_at": datetime(2024, 1, 1, tzinfo=UTC),
        "title": "T",
        "content_text": "x" * 600,
        "ingested_by_id": None,
        "source_type": SourceType.NEWS_REPORT,
        "is_primary": False,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def ranked(stance=Stance.SUPPORTS, score=0.8, authority="ESTABLISHED", **src_kw):
    return SimpleNamespace(
        evidence=SimpleNamespace(id=uuid.uuid4(), stance=stance, directness=Directness.DIRECT),
        source=src(**src_kw),
        score=score,
        components={"authority_level": authority},
    )


def test_weights_sum_to_one_and_cover_required_factors():
    assert set(WEIGHTS) == {
        "authority",
        "primary_source",
        "relevance",
        "recency",
        "directness",
        "corroboration",
        "document_quality",
    }
    assert abs(sum(WEIGHTS.values()) - 1) < 1e-9


def test_recency():
    ref = date(2023, 12, 31)
    assert recency_score(src(published_at=datetime(2024, 1, 5, tzinfo=UTC)), ref)[0] == 1.0
    old, _ = recency_score(src(published_at=datetime(2017, 1, 1, tzinfo=UTC)), ref)
    assert 0 < old < 0.25
    assert recency_score(src(published_at=None), ref) == (0.5, "publication date unknown")


def test_document_quality_signals():
    good, _ = document_quality(src())
    bad, signals = document_quality(
        src(
            title="(untitled)",
            publisher_name=None,
            published_at=None,
            content_text="short",
            url="http://x.example",
            source_type=SourceType.SOCIAL_MEDIA_POST,
        )
    )
    assert good == 1.0 and bad == 0.0
    assert signals["not_social_media"] is False


def _entry(**kw):
    now = datetime.now(UTC)
    base = dict(
        verification_status=RegistryVerificationStatus.VERIFIED,
        review_due_at=now + timedelta(days=30),
        authority_level=AuthorityLevel.PRIMARY_AUTHORITY,
        authority_scope=["literacy", "education"],
    )
    base.update(kw)
    return RegistrySource(**base)


def test_authority_is_scoped_verified_and_expires():
    claim = "Riverland's literacy rate rose to 81 percent"
    assert effective_authority(_entry(), claim).level == AuthorityLevel.PRIMARY_AUTHORITY
    # out of declared scope -> general
    assert effective_authority(_entry(), "Riverland's GDP grew").level == AuthorityLevel.GENERAL
    # unverified or expired -> unassessed
    assert (
        effective_authority(
            _entry(verification_status=RegistryVerificationStatus.UNVERIFIED), claim
        ).level
        == AuthorityLevel.UNASSESSED
    )
    expired = _entry(review_due_at=datetime.now(UTC) - timedelta(days=1))
    assert effective_authority(expired, claim).level == AuthorityLevel.UNASSESSED
    assert effective_authority(None, claim).level == AuthorityLevel.UNASSESSED


def test_normalize_domain():
    assert normalize_domain("https://www.Stats.Example.org/x?y") == "stats.example.org"
    assert normalize_domain("example.org") == "example.org"
    assert normalize_domain(None) is None


def test_calibration_caps_single_source_and_contrary_evidence():
    one = ranked(is_primary=True)
    cal = calibrate(Classification.TRUE, 0.95, [one], [one])
    assert cal.confidence == 0.6
    assert {g["rule"] for g in cal.guardrails} == {"single_source"}

    a = ranked(is_primary=True, url="https://a.example/1")
    b = ranked(url="https://b.example/2")
    contra = ranked(stance=Stance.REFUTES, score=0.7, url="https://c.example/3")
    cal = calibrate(Classification.TRUE, 0.9, [a, b], [a, b, contra])
    assert cal.confidence == 0.5
    assert "strong_contrary_evidence" in {g["rule"] for g in cal.guardrails}

    cal = calibrate(Classification.UNVERIFIED, 0.8, [], [a])
    assert cal.confidence == 0.5


def test_calibration_leaves_well_supported_confidence():
    a = ranked(is_primary=True, url="https://a.example/1")
    b = ranked(url="https://b.example/2")
    cal = calibrate(Classification.TRUE, 0.9, [a, b], [a, b])
    assert cal.confidence == 0.9 and cal.guardrails == []


def test_low_authority_only_cap():
    a = ranked(Stance.REFUTES, authority="UNASSESSED", is_primary=True, url="https://a.example/1")
    b = ranked(Stance.REFUTES, authority="LIMITED", url="https://b.example/2")
    cal = calibrate(Classification.FALSE, 0.9, [a, b], [a, b])
    assert cal.confidence == 0.6
    assert "low_authority_only" in {g["rule"] for g in cal.guardrails}
