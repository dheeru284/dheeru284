"""Minimal row builders for DB tests. They create real rows; nothing is faked."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.domain.enums import ClaimType, UserRole
from app.models import Claim, Submission, User


def make_user(session: Session, role: UserRole = UserRole.ANALYST) -> User:
    user = User(
        email=f"user-{uuid.uuid4().hex[:8]}@example.test", display_name="Test User", role=role
    )
    session.add(user)
    session.flush()
    return user


def make_submission(session: Session, user: User, text: str = "Sample statement.") -> Submission:
    sub = Submission(submitted_by_id=user.id, raw_text=text)
    session.add(sub)
    session.flush()
    return sub


def make_human_claim(session: Session, submission: Submission, user: User) -> Claim:
    claim = Claim(
        submission_id=submission.id,
        text="The state's literacy rate rose in 2021.",
        normalized_text="The state's literacy rate rose in 2021.",
        claim_type=ClaimType.FACTUAL,
        checkworthy=True,
        language="en",
        created_by_id=user.id,
    )
    session.add(claim)
    session.flush()
    return claim
