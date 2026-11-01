"""Claim extraction (FR-2): submission text -> atomic, structured, blinded claims."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.agents.definitions import CLAIM_EXTRACTOR, ClaimExtractionOutput, ExtractedClaim
from app.agents.runner import run_agent
from app.ai.prompts import wrap_untrusted
from app.audit.service import AuditService
from app.domain.enums import ActorType, EntityRole, SubmissionStatus
from app.domain.text import SPEAKER_PLACEHOLDER, blind, grounding_score
from app.models import Claim, Entity, Submission
from app.pipeline.context import PipelineContext

MAX_PROMPT_CHARS = 24_000
MIN_GROUNDING = 0.5


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _original_source(sub: Submission) -> dict:
    return {
        "submission_id": str(sub.id),
        "submission_type": sub.submission_type.value,
        "url": sub.source_url,
        "title": sub.title,
        "publisher": sub.publisher_name,
        "published_at": sub.published_at.isoformat() if sub.published_at else None,
        "extraction_method": sub.extraction_method.value if sub.extraction_method else None,
    }


def extract_claims(
    ctx: PipelineContext, submission: Submission, pipeline_job_id: uuid.UUID | None
) -> list[Claim]:
    session: Session = ctx.session
    text = submission.extracted_text or ""
    speaker = (
        session.get(Entity, submission.speaker_entity_id) if submission.speaker_entity_id else None
    )
    material = text[:MAX_PROMPT_CHARS]
    result = run_agent(
        session,
        ctx.llm,
        CLAIM_EXTRACTOR,
        {
            "language": submission.language,
            "speaker": speaker.name if speaker else "unknown",
            "material": wrap_untrusted("MATERIAL", str(submission.id), material),
        },
        pipeline_job_id=pipeline_job_id,
    )
    output: ClaimExtractionOutput = result.output
    audit = AuditService(session)
    now = datetime.now(UTC)
    claims: list[Claim] = []
    seen: set[str] = set()

    for item in output.claims:
        reason = _reject_reason(item, material, seen)
        if reason:
            audit.record(
                actor_type=ActorType.SYSTEM,
                actor_id="system:extraction_guardrail",
                action="claim.rejected",
                entity_type="submission",
                entity_id=submission.id,
                payload={"text": item.text, "reason": reason, "ai_run_id": str(result.ai_run.id)},
            )
            continue
        seen.add(item.text.strip().lower())
        speaker_names = [e.name for e in item.entities if e.role == EntityRole.SPEAKER]
        if speaker:
            speaker_names.append(speaker.name)
        normalized = blind(item.normalized_text, speaker_names)
        claim = Claim(
            submission_id=submission.id,
            text=item.text.strip(),
            normalized_text=normalized,
            subject=blind(item.subject, speaker_names),
            predicate=item.predicate,
            object_=item.object,
            time_reference=item.time_reference,
            claim_date=_parse_date(item.claim_date),
            location=item.location,
            entities=[e.model_dump(mode="json") for e in item.entities],
            original_source=_original_source(submission),
            claim_type=item.claim_type,
            checkworthy=item.checkworthy,
            language=submission.language,
            speaker_entity_id=submission.speaker_entity_id,
            statement_date=submission.statement_date,
            extraction_ai_run_id=result.ai_run.id,
            extracted_at=now,
        )
        session.add(claim)
        session.flush()
        audit.record(
            actor_type=ActorType.AGENT,
            actor_id=CLAIM_EXTRACTOR.name,
            action="claim.extracted",
            entity_type="claim",
            entity_id=claim.id,
            payload={
                "submission_id": str(submission.id),
                "text": claim.text,
                "normalized_text": claim.normalized_text,
                "subject": claim.subject,
                "predicate": claim.predicate,
                "object": claim.object_,
                "claim_type": claim.claim_type.value,
                "blinded": SPEAKER_PLACEHOLDER in claim.normalized_text,
                "ai_run_id": str(result.ai_run.id),
            },
        )
        claims.append(claim)

    submission.status = SubmissionStatus.PROCESSED if claims else SubmissionStatus.NO_CLAIMS
    session.flush()
    return claims


def _reject_reason(item: ExtractedClaim, material: str, seen: set[str]) -> str | None:
    if item.text.strip().lower() in seen:
        return "duplicate"
    score = grounding_score(item.text, material)
    if score < MIN_GROUNDING:
        return f"not grounded in submitted material (term overlap {score:.2f} < {MIN_GROUNDING})"
    return None
