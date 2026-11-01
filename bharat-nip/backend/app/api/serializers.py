from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.state import review_status_for
from app.models import Claim, Submission
from app.schemas.api import ClaimOut, SubmissionOut
from app.services.factcheck import latest_assessment


def submission_out(sub: Submission) -> SubmissionOut:
    out = SubmissionOut.model_validate(sub)
    out.extracted_chars = len(sub.extracted_text or "")
    return out


def claim_out(db: Session, claim: Claim, *, include_result: bool = True) -> ClaimOut:
    out = ClaimOut.model_validate(claim)
    out.review_status = review_status_for(claim.status)
    if include_result:
        latest = latest_assessment(db, claim.id)
        if latest is not None:
            out.latest_classification = latest.classification
            out.latest_confidence = latest.confidence
    return out


def claims_for_submission(db: Session, submission_id) -> list[Claim]:
    return list(
        db.scalars(
            select(Claim).where(Claim.submission_id == submission_id).order_by(Claim.created_at)
        )
    )
