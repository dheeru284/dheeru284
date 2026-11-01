"""Builds the structured fact-check result (FR-7) from stored records only."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import Stance
from app.domain.state import review_status_for
from app.models import (
    AIRun,
    Assessment,
    AssessmentCitation,
    Claim,
    Critique,
    ReviewDecision,
    ReviewTask,
)
from app.services.ranking import RANKING_VERSION, rank_claim_evidence


def latest_assessment(session: Session, claim_id) -> Assessment | None:
    return session.scalar(
        select(Assessment)
        .where(Assessment.claim_id == claim_id)
        .order_by(Assessment.revision.desc())
        .limit(1)
    )


def provenance(run: AIRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "ai_run_id": str(run.id),
        "agent_name": run.agent_name,
        "agent_version": run.agent_version,
        "provider": run.provider,
        "model": run.model,
        "prompt_id": run.prompt_id,
        "prompt_version": run.prompt_version,
        "prompt_sha256": run.prompt_sha256,
        "is_mock": run.provider == "mock",
    }


def build_fact_check(session: Session, claim: Claim) -> dict[str, Any] | None:
    assessment = latest_assessment(session, claim.id)
    if assessment is None:
        return None
    cited = set(
        session.scalars(
            select(AssessmentCitation.evidence_id).where(
                AssessmentCitation.assessment_id == assessment.id
            )
        )
    )
    ranked = rank_claim_evidence(session, claim)

    def item(r) -> dict[str, Any]:
        ev, src = r.evidence, r.source
        return {
            "evidence_id": str(ev.id),
            "quote": ev.quote,
            "stance": ev.stance.value,
            "directness": ev.directness.value,
            "relevance": ev.relevance,
            "rank_score": r.score,
            "ranking_version": RANKING_VERSION,
            "cited": ev.id in cited,
            "source": {
                "source_id": str(src.id),
                "url": src.url,
                "title": src.title,
                "publisher": src.publisher_name,
                "published_at": src.published_at.isoformat() if src.published_at else None,
                "retrieved_at": src.retrieved_at.isoformat(),
                "source_type": src.source_type.value,
                "is_primary": src.is_primary,
                "authority_level": r.components["authority_level"],
                "content_sha256": src.content_sha256,
            },
        }

    critique = session.scalar(
        select(Critique)
        .where(Critique.assessment_id == assessment.id)
        .order_by(Critique.created_at.desc())
        .limit(1)
    )
    task = session.scalar(
        select(ReviewTask)
        .where(ReviewTask.assessment_id == assessment.id)
        .order_by(ReviewTask.created_at.desc())
        .limit(1)
    )
    decision = (
        session.scalar(select(ReviewDecision).where(ReviewDecision.review_task_id == task.id))
        if task
        else None
    )
    return {
        # --- the structured result (PRODUCT_REQUIREMENTS.md FR-7) ---
        "classification": assessment.classification.value,
        "confidence": assessment.confidence,
        "summary": assessment.summary,
        "reasoning": assessment.reasoning,
        "supporting_evidence": [item(r) for r in ranked if r.evidence.stance == Stance.SUPPORTS],
        "contradicting_evidence": [item(r) for r in ranked if r.evidence.stance == Stance.REFUTES],
        "missing_information": assessment.missing_information,
        "recommended_action": assessment.recommended_action.value,
        # --- context and provenance ---
        "context_evidence": [
            item(r) for r in ranked if r.evidence.stance in (Stance.MIXED, Stance.CONTEXT)
        ],
        "claim_id": str(claim.id),
        "assessment_id": str(assessment.id),
        "revision": assessment.revision,
        "produced_by": assessment.produced_by.value,
        "confidence_raw": assessment.confidence_raw,
        "guardrails": assessment.guardrails,
        "assessment_status": assessment.status.value,
        "review_status": review_status_for(claim.status).value,
        "final_classification": decision.final_classification.value
        if decision and decision.final_classification
        else None,
        "review_decision": {
            "decision": decision.decision.value,
            "final_classification": decision.final_classification.value
            if decision.final_classification
            else None,
            "notes": decision.notes,
            "reviewer_id": str(decision.reviewer_id),
            "decided_at": decision.created_at.isoformat(),
        }
        if decision
        else None,
        "critic": {
            "critique_id": str(critique.id),
            "outcome": critique.outcome.value,
            "agent_outcome": critique.agent_outcome.value,
            "outcome_overridden": critique.outcome_overridden,
            "counter_argument": critique.counter_argument,
            "suggested_classification": critique.suggested_classification.value
            if critique.suggested_classification
            else None,
            "checks": critique.checks,
            "deterministic_findings": critique.deterministic_findings,
            "provenance": provenance(session.get(AIRun, critique.ai_run_id)),
        }
        if critique
        else None,
        "provenance": provenance(
            session.get(AIRun, assessment.ai_run_id) if assessment.ai_run_id else None
        ),
    }
