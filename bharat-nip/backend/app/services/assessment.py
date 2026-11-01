"""Fact-check classification (FR-6/FR-7) with deterministic guardrails.

Never forces a classification: no usable evidence => INSUFFICIENT_EVIDENCE by rule
(no LLM call); non-checkable claims => OPINION / PREDICTION / SATIRE by rule; agent output
is validated (citations, stance consistency) and its confidence is capped by evidence
strength (calibration guardrails), with every applied rule recorded.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.definitions import ASSESSOR, AssessmentProposal
from app.agents.runner import InvalidAgentOutput, run_agent
from app.ai.prompts import wrap_untrusted
from app.audit.service import AuditService
from app.domain.enums import (
    CLASSIFICATIONS_REQUIRING_CITATION,
    NON_CHECKABLE_VERDICT,
    NON_DETERMINATIONS,
    USABLE_STANCES,
    ActorType,
    AssessmentStatus,
    AuthorityLevel,
    Classification,
    ProducedBy,
    RecommendedAction,
    Stance,
)
from app.models import Assessment, AssessmentCitation, Claim, Critique, SearchQuery
from app.pipeline.context import PipelineContext
from app.services.ranking import RankedEvidence, origin_key, rank_claim_evidence

MAX_EVIDENCE_ITEMS = 15
STRONG_EVIDENCE_SCORE = 0.6
LOW_AUTHORITY = {AuthorityLevel.UNASSESSED, AuthorityLevel.LIMITED}


def label_evidence(ranked: list[RankedEvidence]) -> dict[str, RankedEvidence]:
    usable = [r for r in ranked if r.evidence.stance in USABLE_STANCES][:MAX_EVIDENCE_ITEMS]
    return {f"E{i}": r for i, r in enumerate(usable, start=1)}


def render_evidence(labels: dict[str, RankedEvidence]) -> str:
    blocks = []
    for label, r in labels.items():
        src = r.source
        meta = (
            f"Stance: {r.evidence.stance.value} | Directness: {r.evidence.directness.value} | "
            f"Rank score: {r.score:.2f} | Authority: {r.components['authority_level']} | "
            f"Primary source: {'yes' if src.is_primary else 'no'} | "
            f"Published: {src.published_at.date().isoformat() if src.published_at else 'unknown'}"
            f"\nTitle: {src.title}\nPublisher: {src.publisher_name or 'unknown'}\n"
            f"Analyst note: {r.evidence.stance_rationale}\n\nQuote: {r.evidence.quote}"
        )
        blocks.append(wrap_untrusted("EVIDENCE", label, meta))
    return "\n\n".join(blocks)


@dataclass
class Calibration:
    confidence: float
    guardrails: list[dict]


def calibrate(
    classification: Classification,
    confidence: float,
    cited: list[RankedEvidence],
    all_usable: list[RankedEvidence],
) -> Calibration:
    """Cap the agent's confidence by what the evidence can support."""
    caps: list[tuple[float, str, str]] = []
    if classification in NON_DETERMINATIONS:
        caps.append((0.5, "non_determination", f"{classification.value} is not a determination"))
    if classification in CLASSIFICATIONS_REQUIRING_CITATION:
        origins = {origin_key(r.source) for r in cited}
        if len(origins) < 2:
            caps.append((0.6, "single_source", "fewer than two independent origins cited"))
        if not any(r.source.is_primary for r in cited):
            caps.append((0.75, "no_primary_source", "no primary source among cited evidence"))
        if cited and all(
            AuthorityLevel(r.components["authority_level"]) in LOW_AUTHORITY for r in cited
        ):
            caps.append((0.6, "low_authority_only", "all cited origins unassessed or limited"))
        contrary = {
            Classification.TRUE: Stance.REFUTES,
            Classification.MOSTLY_TRUE: Stance.REFUTES,
            Classification.FALSE: Stance.SUPPORTS,
        }.get(classification)
        if contrary and any(
            r.evidence.stance == contrary and r.score >= STRONG_EVIDENCE_SCORE for r in all_usable
        ):
            caps.append(
                (0.5, "strong_contrary_evidence", f"high-ranked {contrary.value} evidence exists")
            )
    capped = confidence
    applied = []
    for cap, rule, detail in caps:
        if capped > cap:
            applied.append({"rule": rule, "detail": f"{detail}; confidence capped at {cap}"})
            capped = cap
    return Calibration(round(capped, 3), applied)


def _next_revision(session: Session, claim: Claim) -> tuple[int, Assessment | None]:
    latest = session.scalar(
        select(Assessment)
        .where(Assessment.claim_id == claim.id)
        .order_by(Assessment.revision.desc())
        .limit(1)
    )
    return (latest.revision + 1 if latest else 0), latest


def _persist(
    session: Session,
    claim: Claim,
    *,
    classification: Classification,
    confidence: float,
    confidence_raw: float | None,
    summary: str,
    reasoning: str,
    missing_information: list[str],
    recommended_action: RecommendedAction,
    guardrails: list[dict],
    produced_by: ProducedBy,
    ai_run_id: uuid.UUID | None,
    cited: list[RankedEvidence],
) -> Assessment:
    revision, previous = _next_revision(session, claim)
    if previous is not None and previous.status in (
        AssessmentStatus.DRAFT,
        AssessmentStatus.CRITIQUED,
        AssessmentStatus.NEEDS_MORE_RESEARCH,
    ):
        previous.status = AssessmentStatus.SUPERSEDED
    assessment = Assessment(
        claim_id=claim.id,
        revision=revision,
        parent_assessment_id=previous.id if previous else None,
        classification=classification,
        confidence=confidence,
        confidence_raw=confidence_raw,
        summary=summary,
        reasoning=reasoning,
        missing_information=missing_information,
        recommended_action=recommended_action,
        guardrails=guardrails,
        produced_by=produced_by,
        ai_run_id=ai_run_id,
        status=AssessmentStatus.DRAFT,
    )
    session.add(assessment)
    session.flush()
    for r in cited:
        session.add(AssessmentCitation(assessment_id=assessment.id, evidence_id=r.evidence.id))
    session.flush()
    AuditService(session).record(
        actor_type=ActorType.AGENT if produced_by == ProducedBy.AGENT else ActorType.SYSTEM,
        actor_id=ASSESSOR.name if produced_by == ProducedBy.AGENT else "system:assessment_rule",
        action="assessment.revised" if revision > 0 else "assessment.created",
        entity_type="assessment",
        entity_id=assessment.id,
        payload={
            "claim_id": str(claim.id),
            "revision": revision,
            "parent_assessment_id": str(previous.id) if previous else None,
            "classification": classification.value,
            "confidence": confidence,
            "confidence_raw": confidence_raw,
            "produced_by": produced_by.value,
            "cited_evidence": [str(r.evidence.id) for r in cited],
            "guardrails": guardrails,
            "ai_run_id": str(ai_run_id) if ai_run_id else None,
        },
    )
    return assessment


def assess_claim(
    ctx: PipelineContext,
    claim: Claim,
    pipeline_job_id: uuid.UUID | None,
    critique: Critique | None = None,
) -> Assessment:
    session = ctx.session

    # Rule 1: non-checkable claims are classified by type, not by an LLM.
    if claim.claim_type in NON_CHECKABLE_VERDICT:
        classification = NON_CHECKABLE_VERDICT[claim.claim_type]
        return _persist(
            session,
            claim,
            classification=classification,
            confidence=0.0,
            confidence_raw=None,
            summary=f"This is classified as {classification.value.lower()}, not a checkable "
            "statement of fact.",
            reasoning=f"The claim extractor typed this claim as {claim.claim_type.value}. "
            "No factual determination was attempted. Confidence 0 means no evidential "
            "determination was made.",
            missing_information=[],
            recommended_action=RecommendedAction.NOT_FACT_CHECKABLE,
            guardrails=[{"rule": "non_checkable_claim", "detail": claim.claim_type.value}],
            produced_by=ProducedBy.RULE,
            ai_run_id=None,
            cited=[],
        )

    ranked = rank_claim_evidence(session, claim)
    labels = label_evidence(ranked)

    # Rule 2: no usable evidence => INSUFFICIENT_EVIDENCE, without asking an LLM.
    if not labels:
        searches = session.execute(
            select(SearchQuery.provider, func.count())
            .where(SearchQuery.claim_id == claim.id)
            .group_by(SearchQuery.provider)
        ).all()
        searched = ", ".join(f"{p} ({n} queries)" for p, n in searches) or "no providers"
        return _persist(
            session,
            claim,
            classification=Classification.INSUFFICIENT_EVIDENCE,
            confidence=0.0,
            confidence_raw=None,
            summary="Not enough relevant evidence was found to assess this claim.",
            reasoning=f"Searched: {searched}. No retrieved passage supported, refuted or "
            "contextualised the claim. The system does not guess.",
            missing_information=[
                "A primary source (official record or dataset) covering the claim's subject "
                "and period.",
                "Independent reporting on the specific figures or events in the claim.",
            ],
            recommended_action=RecommendedAction.GATHER_MORE_EVIDENCE,
            guardrails=[{"rule": "no_usable_evidence", "detail": searched}],
            produced_by=ProducedBy.RULE,
            ai_run_id=None,
            cited=[],
        )

    def validate(p: AssessmentProposal) -> None:
        unknown = sorted(set(p.cited_evidence) - labels.keys())
        if unknown:
            raise InvalidAgentOutput(f"cited_evidence has unknown labels {unknown}")
        stances = {labels[label].evidence.stance for label in p.cited_evidence}
        if p.classification in CLASSIFICATIONS_REQUIRING_CITATION and not p.cited_evidence:
            raise InvalidAgentOutput(f"{p.classification.value} requires cited evidence")
        if (
            p.classification in (Classification.TRUE, Classification.MOSTLY_TRUE)
            and Stance.SUPPORTS not in stances
        ):
            raise InvalidAgentOutput(f"{p.classification.value} must cite a SUPPORTS item")
        if p.classification == Classification.FALSE and Stance.REFUTES not in stances:
            raise InvalidAgentOutput("FALSE must cite a REFUTES item")
        if p.classification in NON_CHECKABLE_VERDICT.values():
            raise InvalidAgentOutput(
                "OPINION/PREDICTION/SATIRE are assigned from claim type, not by the assessor"
            )

    result = run_agent(
        session,
        ctx.llm,
        ASSESSOR,
        {
            "claim": claim.normalized_text,
            "time_reference": claim.time_reference or "not stated",
            "location": claim.location or "not stated",
            "statement_date": claim.statement_date.isoformat()
            if claim.statement_date
            else "unknown",
            "evidence": render_evidence(labels),
            "revision_request": _revision_request(session, critique),
        },
        validate=validate,
        pipeline_job_id=pipeline_job_id,
    )
    p = result.output
    cited = [labels[label] for label in dict.fromkeys(p.cited_evidence)]
    cal = calibrate(p.classification, p.confidence, cited, list(labels.values()))
    action = p.recommended_action
    guardrails = list(cal.guardrails)
    if p.classification in NON_DETERMINATIONS and action == RecommendedAction.CONFIRM_IN_REVIEW:
        action = RecommendedAction.GATHER_MORE_EVIDENCE
        guardrails.append({"rule": "action_for_non_determination", "detail": action.value})
    return _persist(
        session,
        claim,
        classification=p.classification,
        confidence=cal.confidence,
        confidence_raw=p.confidence,
        summary=p.summary,
        reasoning=p.reasoning,
        missing_information=p.missing_information,
        recommended_action=action,
        guardrails=guardrails,
        produced_by=ProducedBy.AGENT,
        ai_run_id=result.ai_run.id,
        cited=cited,
    )


def _revision_request(session: Session, critique: Critique | None) -> str:
    if critique is None:
        return ""
    previous = session.get(Assessment, critique.assessment_id)
    failed = [c for c in critique.checks if not c.get("passed")]
    return (
        "\nREVISION REQUESTED. An independent critic reviewed your previous assessment.\n"
        f"Previous classification: {previous.classification.value if previous else '?'}\n"
        f"Previous summary: {previous.summary if previous else ''}\n"
        f"Critic's failed checks: {json.dumps(failed, ensure_ascii=False)}\n"
        f"Critic's counter-argument: {critique.counter_argument}\n"
        "Produce a corrected assessment. If the evidence cannot settle the claim, say so."
    )
