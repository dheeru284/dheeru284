"""Allowed claim status transitions (DATABASE_DESIGN.md §4).

Services must call :func:`assert_transition` before changing ``claims.status``.
"""

from __future__ import annotations

from app.domain.enums import ClaimStatus as S

CLAIM_TRANSITIONS: dict[S, frozenset[S]] = {
    # Non-checkable claims (OPINION/PREDICTION/SATIRE) go straight to ASSESSING.
    S.EXTRACTED: frozenset({S.RETRIEVING, S.ASSESSING, S.FAILED}),
    S.RETRIEVING: frozenset({S.EVIDENCE_READY, S.FAILED}),
    S.EVIDENCE_READY: frozenset({S.ASSESSING, S.RETRIEVING, S.FAILED}),
    S.ASSESSING: frozenset({S.CRITIQUING, S.FAILED}),
    # CRITIQUING -> ASSESSING is the bounded REVISE loop.
    S.CRITIQUING: frozenset({S.ASSESSING, S.NEEDS_REVIEW, S.FAILED}),
    S.NEEDS_REVIEW: frozenset({S.IN_REVIEW}),
    # IN_REVIEW -> NEEDS_REVIEW: reviewer released the task.
    # IN_REVIEW -> EVIDENCE_READY: REQUEST_MORE_EVIDENCE.
    S.IN_REVIEW: frozenset({S.APPROVED, S.REJECTED, S.EVIDENCE_READY, S.NEEDS_REVIEW}),
    # A failed claim always goes to a human.
    S.FAILED: frozenset({S.NEEDS_REVIEW}),
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
