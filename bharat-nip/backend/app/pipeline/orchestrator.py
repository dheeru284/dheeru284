"""Deterministic pipeline orchestrator (ARCHITECTURE.md §4.4). Not an LLM.

submission -> CONTENT -> EXTRACTION -> per claim:
  SEARCH -> EVIDENCE -> RANKING -> ASSESSMENT -> CRITIQUE (-> ASSESSMENT, bounded)
  -> REVIEW_ROUTING -> PENDING_REVIEW (a human decides).

Each stage execution is a pipeline_jobs row. The session is committed at stage
boundaries. A failing stage keeps what it recorded (ai_runs, searches) and sends the
claim to a human with reason STAGE_FAILURE; nothing is silently retried forever.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.agents.runner import AgentFailed
from app.audit.service import AuditService
from app.domain.enums import (
    NON_CHECKABLE_VERDICT,
    ActorType,
    ClaimStatus,
    Classification,
    CriticOutcome,
    PipelineJobStatus,
    PipelineStage,
    ProducedBy,
    ReviewReason,
    SubmissionStatus,
)
from app.models import Assessment, Claim, PipelineJob, Source, Submission
from app.pipeline.context import PipelineContext
from app.providers.base import ProviderError
from app.services.assessment import assess_claim
from app.services.content import ContentUnavailable, process_content
from app.services.critic import critique_assessment
from app.services.extraction import extract_claims
from app.services.factcheck import latest_assessment
from app.services.ranking import persist_rankings
from app.services.research import analyse_evidence, search_sources
from app.services.review import route_to_review, set_claim_status

log = logging.getLogger(__name__)
T = TypeVar("T")
STAGE_ATTEMPTS = 2  # transient provider errors only
LOW_CONFIDENCE = 0.5
SYSTEM = "system:orchestrator"


class StageFailed(Exception):
    def __init__(self, stage: PipelineStage, detail: str) -> None:
        super().__init__(f"{stage.value} failed: {detail}")
        self.stage = stage
        self.detail = detail


def _transient(exc: Exception) -> bool:
    return isinstance(exc, ProviderError) or (
        isinstance(exc, AgentFailed) and isinstance(exc.__cause__, ProviderError)
    )


def run_stage[T](
    ctx: PipelineContext,
    stage: PipelineStage,
    fn: Callable[[uuid.UUID], T],
    *,
    submission_id: uuid.UUID | None = None,
    claim_id: uuid.UUID | None = None,
) -> T:
    session = ctx.session
    for attempt in range(1, STAGE_ATTEMPTS + 1):
        job = PipelineJob(
            submission_id=submission_id,
            claim_id=claim_id,
            stage=stage,
            status=PipelineJobStatus.RUNNING,
            attempt=attempt,
            max_attempts=STAGE_ATTEMPTS,
            started_at=datetime.now(UTC),
        )
        session.add(job)
        session.flush()
        try:
            result = fn(job.id)
        except SQLAlchemyError as exc:
            session.rollback()
            _record_failed_job(ctx, stage, submission_id, claim_id, attempt, str(exc))
            raise StageFailed(stage, f"database error: {exc}") from exc
        except Exception as exc:
            job.status = PipelineJobStatus.FAILED
            job.error = f"{type(exc).__name__}: {exc}"[:4000]
            job.finished_at = datetime.now(UTC)
            session.commit()
            if _transient(exc) and attempt < STAGE_ATTEMPTS:
                log.warning("stage %s attempt %s failed transiently: %s", stage, attempt, exc)
                continue
            raise StageFailed(stage, job.error) from exc
        job.status = PipelineJobStatus.SUCCEEDED
        job.finished_at = datetime.now(UTC)
        session.commit()
        return result
    raise AssertionError("unreachable")


def _record_failed_job(ctx, stage, submission_id, claim_id, attempt, error) -> None:
    ctx.session.add(
        PipelineJob(
            submission_id=submission_id,
            claim_id=claim_id,
            stage=stage,
            status=PipelineJobStatus.FAILED,
            attempt=attempt,
            max_attempts=STAGE_ATTEMPTS,
            error=error[:4000],
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
    )
    ctx.session.commit()


# --- submission ----------------------------------------------------------------------------


def process_submission(ctx: PipelineContext, submission_id: uuid.UUID) -> list[uuid.UUID]:
    session = ctx.session
    sub = session.get(Submission, submission_id)
    if sub is None:
        raise ValueError(f"submission {submission_id} not found")
    sub.status = SubmissionStatus.PROCESSING
    session.commit()

    def content(_job_id: uuid.UUID) -> bool:
        try:
            process_content(ctx, sub)
        except ContentUnavailable:
            return False
        return True

    try:
        has_text = run_stage(ctx, PipelineStage.CONTENT, content, submission_id=sub.id)
        if not has_text:
            sub.status = SubmissionStatus.NEEDS_TRANSCRIPTION
            session.commit()
            return []
        claims = run_stage(
            ctx,
            PipelineStage.EXTRACTION,
            lambda job_id: extract_claims(ctx, sub, job_id),
            submission_id=sub.id,
        )
    except StageFailed as exc:
        sub = session.get(Submission, submission_id)
        sub.status = SubmissionStatus.FAILED
        sub.extraction_notes = exc.detail[:2000]
        AuditService(session).record(
            actor_type=ActorType.SYSTEM,
            actor_id=SYSTEM,
            action="submission.failed",
            entity_type="submission",
            entity_id=sub.id,
            payload={"stage": exc.stage.value, "error": exc.detail[:2000]},
        )
        session.commit()
        return []

    claim_ids = [c.id for c in claims]
    for claim_id in claim_ids:
        process_claim(ctx, claim_id)
    return claim_ids


# --- claim ---------------------------------------------------------------------------------


def process_claim(ctx: PipelineContext, claim_id: uuid.UUID) -> None:
    session = ctx.session
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise ValueError(f"claim {claim_id} not found")
    try:
        _research(ctx, claim)
        _assess_and_critique(ctx, claim)
    except StageFailed as exc:
        claim = session.get(Claim, claim_id)
        if claim.status != ClaimStatus.FAILED:
            set_claim_status(session, claim, ClaimStatus.FAILED, SYSTEM)
        route_to_review(
            session,
            claim,
            latest_assessment(session, claim.id),
            ReviewReason.STAGE_FAILURE,
            f"{exc.stage.value}: {exc.detail}"[:2000],
        )
        session.commit()


def _research(ctx: PipelineContext, claim: Claim) -> None:
    session = ctx.session
    if claim.status not in (ClaimStatus.EXTRACTED, ClaimStatus.NEEDS_MORE_RESEARCH):
        raise ValueError(f"claim is {claim.status.value}; research cannot start")
    if claim.claim_type in NON_CHECKABLE_VERDICT and claim.status == ClaimStatus.EXTRACTED:
        set_claim_status(session, claim, ClaimStatus.ASSESSING, SYSTEM)
        session.commit()
        return
    set_claim_status(session, claim, ClaimStatus.RESEARCHING, SYSTEM)
    session.commit()
    source_ids = run_stage(
        ctx,
        PipelineStage.SEARCH,
        lambda job_id: [s.id for s in search_sources(ctx, claim, job_id)],
        claim_id=claim.id,
    )
    run_stage(
        ctx,
        PipelineStage.EVIDENCE,
        lambda job_id: analyse_evidence(
            ctx,
            claim,
            list(session.scalars(select(Source).where(Source.id.in_(source_ids)))),
            job_id,
        ),
        claim_id=claim.id,
    )
    run_stage(
        ctx,
        PipelineStage.RANKING,
        lambda _job_id: persist_rankings(session, claim),
        claim_id=claim.id,
    )
    set_claim_status(session, claim, ClaimStatus.ASSESSING, SYSTEM)
    session.commit()


def _route(ctx: PipelineContext, claim: Claim, assessment: Assessment, reason, detail=None):
    run_stage(
        ctx,
        PipelineStage.REVIEW_ROUTING,
        lambda _job_id: route_to_review(ctx.session, claim, assessment, reason, detail),
        claim_id=claim.id,
    )


def _routine_reason(assessment: Assessment) -> ReviewReason:
    if assessment.classification in (
        Classification.INSUFFICIENT_EVIDENCE,
        Classification.UNVERIFIED,
    ):
        return ReviewReason.INSUFFICIENT_EVIDENCE
    if assessment.produced_by == ProducedBy.AGENT and assessment.confidence < LOW_CONFIDENCE:
        return ReviewReason.LOW_CONFIDENCE
    return ReviewReason.ROUTINE


def _assess_and_critique(ctx: PipelineContext, claim: Claim) -> None:
    session = ctx.session
    max_revisions = ctx.settings.max_revision_rounds
    critique = None
    for round_no in range(max_revisions + 1):
        assessment = run_stage(
            ctx,
            PipelineStage.ASSESSMENT,
            lambda job_id, c=critique: assess_claim(ctx, claim, job_id, c),
            claim_id=claim.id,
        )
        if assessment.produced_by == ProducedBy.RULE:
            # Nothing for a critic to disprove: no agent reasoning. A human still reviews.
            _route(ctx, claim, assessment, _routine_reason(assessment))
            return
        set_claim_status(session, claim, ClaimStatus.CRITIQUING, SYSTEM)
        session.commit()
        critique = run_stage(
            ctx,
            PipelineStage.CRITIQUE,
            lambda job_id, a=assessment: critique_assessment(ctx, a, job_id),
            claim_id=claim.id,
        )
        if critique.outcome == CriticOutcome.PASS:
            _route(ctx, claim, assessment, _routine_reason(assessment))
            return
        if critique.outcome == CriticOutcome.ESCALATE:
            reason = (
                ReviewReason.RULE_FLAG
                if critique.outcome_overridden
                else ReviewReason.CRITIC_ESCALATION
            )
            _route(ctx, claim, assessment, reason, critique.summary)
            return
        # REVISE
        if round_no < max_revisions:
            set_claim_status(session, claim, ClaimStatus.ASSESSING, SYSTEM)
            session.commit()
            continue
        _route(
            ctx,
            claim,
            assessment,
            ReviewReason.LOOP_LIMIT,
            f"critic still requested revision after {max_revisions} revision(s): "
            f"{critique.summary}",
        )
        return
