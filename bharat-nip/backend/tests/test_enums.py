from app.domain.enums import (
    NON_CHECKABLE_VERDICT,
    VERDICTS_REQUIRING_CITATION,
    ClaimType,
    Verdict,
)


def test_verdict_taxonomy_is_exactly_the_documented_set():
    # PRODUCT_REQUIREMENTS.md §4. Changing this set is a product decision.
    assert {v.value for v in Verdict} == {
        "TRUE",
        "MOSTLY_TRUE",
        "MISLEADING",
        "OUT_OF_CONTEXT",
        "FALSE",
        "UNVERIFIED",
        "INSUFFICIENT_EVIDENCE",
        "OPINION",
        "PREDICTION",
        "SATIRE",
    }


def test_uncertain_verdicts_do_not_require_citations():
    for v in (Verdict.UNVERIFIED, Verdict.INSUFFICIENT_EVIDENCE, Verdict.OPINION):
        assert v not in VERDICTS_REQUIRING_CITATION
    assert Verdict.FALSE in VERDICTS_REQUIRING_CITATION
    assert Verdict.TRUE in VERDICTS_REQUIRING_CITATION


def test_non_checkable_claim_types_map_to_verdicts():
    assert NON_CHECKABLE_VERDICT == {
        ClaimType.OPINION: Verdict.OPINION,
        ClaimType.PREDICTION: Verdict.PREDICTION,
        ClaimType.SATIRE: Verdict.SATIRE,
    }
