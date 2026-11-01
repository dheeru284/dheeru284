"""Object-level access rules shared by routes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.auth import has_role
from app.domain.enums import ClaimStatus, UserRole
from app.models import Claim, Submission, User
from app.services.errors import Forbidden, NotFound


def can_see_all(user: User) -> bool:
    return has_role(user, UserRole.ANALYST)


def get_visible_submission(db: Session, user: User, submission_id) -> Submission:
    sub = db.get(Submission, submission_id)
    if sub is None or (not can_see_all(user) and sub.submitted_by_id != user.id):
        raise NotFound("Submission not found.")
    return sub


def get_visible_claim(db: Session, user: User, claim_id) -> Claim:
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise NotFound("Claim not found.")
    if not can_see_all(user):
        sub = db.get(Submission, claim.submission_id)
        if sub.submitted_by_id != user.id:
            raise NotFound("Claim not found.")
    return claim


def require_result_visible(user: User, claim: Claim) -> None:
    """Submitters see evidence and results only after a human approved them."""
    if not can_see_all(user) and claim.status != ClaimStatus.APPROVED:
        raise Forbidden("Results are visible to submitters once a reviewer has approved them.")
