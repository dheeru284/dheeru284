import pytest

from app.domain.enums import ClaimStatus as S
from app.domain.state import (
    CLAIM_TRANSITIONS,
    TERMINAL_STATUSES,
    InvalidTransition,
    assert_transition,
    can_transition,
)


def test_every_status_has_a_transition_entry():
    assert set(CLAIM_TRANSITIONS) == set(S)


def test_terminal_statuses():
    assert {S.APPROVED, S.REJECTED} == TERMINAL_STATUSES


def test_approval_only_from_human_review():
    sources = {s for s, nxt in CLAIM_TRANSITIONS.items() if S.APPROVED in nxt}
    assert sources == {S.IN_REVIEW}


def test_rejection_only_from_human_review():
    sources = {s for s, nxt in CLAIM_TRANSITIONS.items() if S.REJECTED in nxt}
    assert sources == {S.IN_REVIEW}


def test_failure_routes_to_human():
    assert CLAIM_TRANSITIONS[S.FAILED] == {S.NEEDS_REVIEW}


def test_revise_loop_and_non_checkable_shortcut():
    assert can_transition(S.CRITIQUING, S.ASSESSING)
    assert can_transition(S.EXTRACTED, S.ASSESSING)


def test_invalid_transition_raises():
    with pytest.raises(InvalidTransition, match="APPROVED"):
        assert_transition(S.APPROVED, S.ASSESSING)
    with pytest.raises(InvalidTransition):
        assert_transition(S.ASSESSING, S.APPROVED)


def test_every_non_terminal_status_can_reach_review():
    def reachable(start: S) -> set[S]:
        seen, stack = set(), [start]
        while stack:
            cur = stack.pop()
            for nxt in CLAIM_TRANSITIONS[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    for status in set(S) - TERMINAL_STATUSES - {S.NEEDS_REVIEW, S.IN_REVIEW}:
        assert S.NEEDS_REVIEW in reachable(status), status
