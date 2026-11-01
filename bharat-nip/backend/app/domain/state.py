"""Allowed claim status transitions (DATABASE_DESIGN.md §4).

Services must go through :func:`assert_transition` before changing ``claims.status``.
"""

from __future__ import annotations

from app.domain.enums import ClaimStatus as S
from app.domain.enums import ReviewStatus

CLAIM_TRANSITIONS: dict[S, frozenset[S]] = {
    # Non-checkable claims (OPINION/PREDICTION/SATIRE) go straight to ASSESSING.
    S.EXTRACTED: frozenset({S.RESEARCHING, S.ASSESSING, S.FAILED}),
    S.RESEARCHING: frozenset({S.ASSESSING, S.FAILED}),
    # ASSESSING -> PENDING_REVIEW: rule-produced assessments skip the critic.
    S.ASSESSING: frozenset({S.CRITIQUING, S.PENDING_REVIEW, S.FAILED}),
    # CRITIQUING -> ASSESSING is the bounded REVISE loop.
    S.CRITIQUING: frozenset({S.ASSESSING, S.PENDING_REVIEW, S.FAILED}),
    S.PENDING_REVIEW: frozenset({S.APPROVED, S.REJECTED, S.NEEDS_MORE_RESEARCH}),
    S.NEEDS_MORE_RESEARCH: frozenset({S.RESEARCHING}),
    # A failed claim always goes to a human.
    S.FAILED: frozenset({S.PENDING_REVIEW}),
    S.APPROVED: frozenset(),
    S.REJECTED: frozenset(),
}

TERMINAL_STATUSES = frozenset(s for s, nxt in CLAIM_TRANSITIONS.items() if not nxt)


class InvalidTransition(Exception):
    def __init__(self, current: S, target: S) -> None:
        super().__init__(f"Claim is {current}; cannot move to {target}")
        self.current = current
        self.target = target


def can_transition(current: S, target: S) -> bool:
    return target in CLAIM_TRANSITIONS[current]


def assert_transition(current: S, target: S) -> None:
    if not can_transition(current, target):
        raise InvalidTransition(current, target)


def review_status_for(status: S) -> ReviewStatus:
    return {
        S.PENDING_REVIEW: ReviewStatus.PENDING_REVIEW,
        S.APPROVED: ReviewStatus.APPROVED,
        S.REJECTED: ReviewStatus.REJECTED,
        S.NEEDS_MORE_RESEARCH: ReviewStatus.NEEDS_MORE_RESEARCH,
    }.get(status, ReviewStatus.NOT_READY)
