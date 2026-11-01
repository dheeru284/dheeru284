import pytest

from app.domain.enums import ClaimStatus as S
from app.domain.enums import ReviewStatus
from app.domain.state import (
    CLAIM_TRANSITIONS,
    TERMINAL_STATUSES,
    InvalidTransition,
    assert_transition,
    can_transition,
    review_status_for,
)


def test_every_status_has_a_transition_entry():
    assert set(CLAIM_TRANSITIONS) == set(S)


def test_terminal_statuses():
    assert {S.APPROVED, S.REJECTED} == TERMINAL_STATUSES


@pytest.mark.parametrize("target", [S.APPROVED, S.REJECTED, S.NEEDS_MORE_RESEARCH])
def test_human_outcomes_only_from_pending_review(target):
    sources = {s for s, nxt in CLAIM_TRANSITIONS.items() if target in nxt}
    assert sources == {S.PENDING_REVIEW}


def test_failure_routes_to_human():
    assert CLAIM_TRANSITIONS[S.FAILED] == {S.PENDING_REVIEW}


def test_revise_loop_and_non_checkable_shortcut():
    assert can_transition(S.CRITIQUING, S.ASSESSING)
    assert can_transition(S.EXTRACTED, S.ASSESSING)
    assert can_transition(S.NEEDS_MORE_RESEARCH, S.RESEARCHING)


def test_invalid_transition_raises():
    with pytest.raises(InvalidTransition, match="APPROVED"):
        assert_transition(S.APPROVED, S.ASSESSING)
    with pytest.raises(InvalidTransition):
        assert_transition(S.CRITIQUING, S.APPROVED)


def test_every_non_terminal_status_can_reach_review():
    def reachable(start: S) -> set[S]:
        seen, stack = set(), [start]
        while stack:
            for nxt in CLAIM_TRANSITIONS[stack.pop()]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    for status in set(S) - TERMINAL_STATUSES - {S.PENDING_REVIEW}:
        assert S.PENDING_REVIEW in reachable(status), status


def test_review_status_mapping():
    assert review_status_for(S.PENDING_REVIEW) == ReviewStatus.PENDING_REVIEW
    assert review_status_for(S.APPROVED) == ReviewStatus.APPROVED
    assert review_status_for(S.REJECTED) == ReviewStatus.REJECTED
    assert review_status_for(S.NEEDS_MORE_RESEARCH) == ReviewStatus.NEEDS_MORE_RESEARCH
    assert review_status_for(S.ASSESSING) == ReviewStatus.NOT_READY
