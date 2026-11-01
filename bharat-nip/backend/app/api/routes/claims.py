from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.access import can_see_all, get_visible_claim, require_result_visible
from app.api.auth import Analyst, CurrentUser
from app.api.deps import get_db, get_dispatcher
from app.api.serializers import claim_out
from app.domain.enums import ClaimStatus, ClaimType, ReviewStatus, ReviewTaskStatus
from app.domain.state import review_status_for
from app.models import (
    AIRun,
    Assessment,
    AssessmentCitation,
    AuditEvent,
    Claim,
    Critique,
    EvidenceRanking,
    PipelineJob,
    ReviewTask,
    SearchQuery,
    SearchResult,
    Submission,
)
from app.pipeline.dispatch import PipelineDispatcher
from app.schemas.api import (
    AssessmentOut,
    AuditEventOut,
    ClaimDetail,
    ClaimOut,
    EvidenceOut,
    Page,
    PipelineJobOut,
    SearchQueryOut,
    SearchResultOut,
    decode_cursor,
    encode_cursor,
)
from app.services.errors import Conflict, NotFound
from app.services.factcheck import build_fact_check
from app.services.ranking import RANKING_VERSION, rank_claim_evidence

router = APIRouter(tags=["claims"])
DB = Annotated[Session, Depends(get_db)]

_REVIEW_TO_STATUS = {
    ReviewStatus.PENDING_REVIEW: [ClaimStatus.PENDING_REVIEW],
    ReviewStatus.APPROVED: [ClaimStatus.APPROVED],
    ReviewStatus.REJECTED: [ClaimStatus.REJECTED],
    ReviewStatus.NEEDS_MORE_RESEARCH: [ClaimStatus.NEEDS_MORE_RESEARCH],
    ReviewStatus.NOT_READY: [
        s
        for s in ClaimStatus
        if s
        not in (
            ClaimStatus.PENDING_REVIEW,
            ClaimStatus.APPROVED,
            ClaimStatus.REJECTED,
            ClaimStatus.NEEDS_MORE_RESEARCH,
        )
    ],
}


@router.get("/claims", response_model=Page[ClaimOut])
def list_claims(
    user: CurrentUser,
    db: DB,
    status: ClaimStatus | None = None,
    review_status: ReviewStatus | None = None,
    claim_type: ClaimType | None = None,
    submission_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
):
    offset = decode_cursor(cursor)
    q = select(Claim).order_by(Claim.created_at.desc(), Claim.id)
    if not can_see_all(user):
        q = q.join(Submission, Submission.id == Claim.submission_id).where(
            Submission.submitted_by_id == user.id
        )
    if status:
        q = q.where(Claim.status == status)
    if review_status:
        q = q.where(Claim.status.in_(_REVIEW_TO_STATUS[review_status]))
    if claim_type:
        q = q.where(Claim.claim_type == claim_type)
    if submission_id:
        q = q.where(Claim.submission_id == submission_id)
    rows = db.scalars(q.offset(offset).limit(limit + 1)).all()
    return Page(
        items=[
            claim_out(db, c, include_result=can_see_all(user) or c.status == ClaimStatus.APPROVED)
            for c in rows[:limit]
        ],
        next_cursor=encode_cursor(offset + limit) if len(rows) > limit else None,
    )


@router.get("/claims/{claim_id}", response_model=ClaimDetail)
def get_claim(claim_id: uuid.UUID, user: CurrentUser, db: DB):
    claim = get_visible_claim(db, user, claim_id)
    jobs = db.scalars(
        select(PipelineJob).where(PipelineJob.claim_id == claim.id).order_by(PipelineJob.created_at)
    ).all()
    open_task = db.scalar(
        select(ReviewTask.id).where(
            ReviewTask.claim_id == claim.id, ReviewTask.status == ReviewTaskStatus.OPEN
        )
    )
    return ClaimDetail(
        claim=claim_out(db, claim, include_result=can_see_all(user) or claim.status == "APPROVED"),
        pipeline_jobs=[PipelineJobOut.model_validate(j) for j in jobs],
        open_review_task_id=open_task,
    )


@router.get("/claims/{claim_id}/fact-check")
def get_fact_check(claim_id: uuid.UUID, user: CurrentUser, db: DB) -> dict[str, Any]:
    """The structured fact-check result for the latest assessment."""
    claim = get_visible_claim(db, user, claim_id)
    require_result_visible(user, claim)
    result = build_fact_check(db, claim)
    if result is None:
        raise NotFound(
            f"No assessment yet (claim is {claim.status.value}, review status "
            f"{review_status_for(claim.status).value})."
        )
    return result


@router.get("/claims/{claim_id}/evidence", response_model=list[EvidenceOut])
def get_evidence(claim_id: uuid.UUID, user: CurrentUser, db: DB):
    claim = get_visible_claim(db, user, claim_id)
    require_result_visible(user, claim)
    stored = {
        r.evidence_id: r
        for r in db.scalars(
            select(EvidenceRanking).where(EvidenceRanking.ranking_version == RANKING_VERSION)
        )
    }
    out = []
    for r in rank_claim_evidence(db, claim):
        ev, src = r.evidence, r.source
        saved = stored.get(ev.id)
        out.append(
            EvidenceOut(
                id=ev.id,
                quote=ev.quote,
                quote_char_start=ev.quote_char_start,
                quote_char_end=ev.quote_char_end,
                stance=ev.stance.value,
                stance_rationale=ev.stance_rationale,
                directness=ev.directness.value,
                relevance=ev.relevance,
                lexical_relevance=ev.lexical_relevance,
                agent_relevance=ev.agent_relevance,
                extracted_by_ai_run_id=ev.extracted_by_ai_run_id,
                rank_score=saved.score if saved else r.score,
                rank_components=saved.components if saved else r.components,
                source={
                    "id": str(src.id),
                    "url": src.url,
                    "title": src.title,
                    "publisher": src.publisher_name,
                    "published_at": src.published_at.isoformat() if src.published_at else None,
                    "retrieved_at": src.retrieved_at.isoformat(),
                    "source_type": src.source_type.value,
                    "is_primary": src.is_primary,
                    "content_sha256": src.content_sha256,
                    "registry_source_id": str(src.registry_source_id)
                    if src.registry_source_id
                    else None,
                },
            )
        )
    return out


@router.get("/claims/{claim_id}/assessments", response_model=list[AssessmentOut])
def get_assessments(claim_id: uuid.UUID, user: CurrentUser, db: DB):
    claim = get_visible_claim(db, user, claim_id)
    require_result_visible(user, claim)
    out = []
    for a in db.scalars(
        select(Assessment).where(Assessment.claim_id == claim.id).order_by(Assessment.revision)
    ):
        item = AssessmentOut.model_validate(a)
        item.cited_evidence_ids = list(
            db.scalars(
                select(AssessmentCitation.evidence_id).where(
                    AssessmentCitation.assessment_id == a.id
                )
            )
        )
        item.critiques = [
            {
                "id": str(c.id),
                "outcome": c.outcome.value,
                "agent_outcome": c.agent_outcome.value,
                "outcome_overridden": c.outcome_overridden,
                "checks": c.checks,
                "deterministic_findings": c.deterministic_findings,
                "counter_argument": c.counter_argument,
                "suggested_classification": c.suggested_classification.value
                if c.suggested_classification
                else None,
                "summary": c.summary,
                "ai_run_id": str(c.ai_run_id),
                "created_at": c.created_at.isoformat(),
            }
            for c in db.scalars(
                select(Critique).where(Critique.assessment_id == a.id).order_by(Critique.created_at)
            )
        ]
        out.append(item)
    return out


@router.get("/claims/{claim_id}/searches", response_model=list[SearchQueryOut])
def get_searches(claim_id: uuid.UUID, _: Analyst, db: DB):
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise NotFound("Claim not found.")
    out = []
    for q in db.scalars(
        select(SearchQuery)
        .where(SearchQuery.claim_id == claim.id)
        .order_by(SearchQuery.executed_at)
    ):
        item = SearchQueryOut.model_validate(q)
        item.results = [
            SearchResultOut.model_validate(r)
            for r in db.scalars(
                select(SearchResult)
                .where(SearchResult.search_query_id == q.id)
                .order_by(SearchResult.rank)
            )
        ]
        out.append(item)
    return out


@router.get("/claims/{claim_id}/audit", response_model=list[AuditEventOut])
def get_claim_audit(claim_id: uuid.UUID, _: Analyst, db: DB):
    """Audit events about this claim and everything derived from it, in order."""
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise NotFound("Claim not found.")
    cid = str(claim.id)
    ids = {cid, str(claim.submission_id)}
    ids |= {
        str(i) for i in db.scalars(select(Assessment.id).where(Assessment.claim_id == claim.id))
    }
    ids |= {
        str(i) for i in db.scalars(select(ReviewTask.id).where(ReviewTask.claim_id == claim.id))
    }
    # Agent executions for this claim: extraction, evidence analysis, assessment, critique.
    run_ids = {claim.extraction_ai_run_id}
    run_ids |= set(
        db.scalars(
            select(AIRun.id)
            .join(PipelineJob, PipelineJob.id == AIRun.pipeline_job_id)
            .where(PipelineJob.claim_id == claim.id)
        )
    )
    ids |= {str(i) for i in run_ids if i}
    events = db.scalars(
        select(AuditEvent)
        .where(
            (AuditEvent.entity_id.in_(ids))
            | (AuditEvent.payload["claim_id"].astext == cid)
            | (AuditEvent.payload["assessment_id"].astext.in_(ids))
        )
        .order_by(AuditEvent.seq)
    ).all()
    return events


@router.post("/claims/{claim_id}/research", response_model=ClaimOut, status_code=202)
def rerun_research(
    claim_id: uuid.UUID,
    _: Analyst,
    db: DB,
    dispatcher: Annotated[PipelineDispatcher, Depends(get_dispatcher)],
):
    """Re-run research and assessment for a claim a reviewer sent back."""
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise NotFound("Claim not found.")
    if claim.status != ClaimStatus.NEEDS_MORE_RESEARCH:
        raise Conflict(f"Claim is {claim.status.value}; only NEEDS_MORE_RESEARCH can be re-run.")
    dispatcher.rerun_claim(claim.id)
    db.refresh(claim)
    return claim_out(db, claim)
