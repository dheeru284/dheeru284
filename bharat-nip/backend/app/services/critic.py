"""FactCheckCriticAgent (FR-8): an independent critic that tries to disprove an assessment.

Independence: a different agent identity and prompt, optionally a different model
(BNIP_OLLAMA_CRITIC_MODEL); it sees the assessment's output, never the assessor's
messages. Deterministic findings are computed first, given to the critic, and enforced:
if a HIGH-severity finding exists, a critic PASS is overridden to ESCALATE.
"""

from __future__ import annotations

import json
import uuid
from datetime import date

from sqlalchemy import select

from app.agents.definitions import ASSESSOR, FACT_CHECK_CRITIC, CritiqueProposal
from app.agents.runner import InvalidAgentOutput, run_agent
from app.audit.service import AuditService
from app.domain.enums import (
    CLASSIFICATIONS_REQUIRING_CITATION,
    ActorType,
    AssessmentStatus,
    AuthorityLevel,
    Classification,
    CriticCheck,
    CriticOutcome,
    FindingSeverity,
    ProducedBy,
    Stance,
)
from app.models import AIRun, Assessment, AssessmentCitation, Claim, Critique
from app.pipeline.context import PipelineContext
from app.services.assessment import LOW_AUTHORITY, label_evidence, render_evidence
from app.services.ranking import (
    OUTDATED_AFTER_YEARS,
    RankedEvidence,
    evidence_age_years,
    origin_key,
    rank_claim_evidence,
    reference_date,
)

CONTRARY_SCORE = 0.5


class SelfReviewError(Exception):
    """Raised if the critic would review its own work."""


def deterministic_findings(
    assessment: Assessment,
    cited: list[RankedEvidence],
    usable: list[RankedEvidence],
    ref: date,
) -> list[dict]:
    findings: list[dict] = []

    def add(check: CriticCheck, severity: FindingSeverity, detail: str, ev: list[str]) -> None:
        findings.append(
            {"check": check.value, "severity": severity.value, "detail": detail, "evidence": ev}
        )

    c = assessment.classification
    cited_ids = {r.evidence.id for r in cited}
    contrary = {
        Classification.TRUE: Stance.REFUTES,
        Classification.MOSTLY_TRUE: Stance.REFUTES,
        Classification.FALSE: Stance.SUPPORTS,
    }.get(c)
    if contrary:
        ignored = [
            r
            for r in usable
            if r.evidence.stance == contrary
            and r.evidence.id not in cited_ids
            and r.score >= CONTRARY_SCORE
        ]
        if ignored:
            add(
                CriticCheck.CONTRADICTORY_EVIDENCE,
                FindingSeverity.HIGH,
                f"{len(ignored)} uncited {contrary.value} item(s) with rank >= {CONTRARY_SCORE}",
                [str(r.evidence.id) for r in ignored],
            )
    outdated = [
        r
        for r in cited
        if (age := evidence_age_years(r.source, ref)) is not None and age > OUTDATED_AFTER_YEARS
    ]
    if outdated:
        add(
            CriticCheck.OUTDATED_EVIDENCE,
            FindingSeverity.MEDIUM,
            f"{len(outdated)} cited item(s) published more than {OUTDATED_AFTER_YEARS:.0f} years "
            f"before the reference date {ref.isoformat()}",
            [str(r.evidence.id) for r in outdated],
        )
    if c in CLASSIFICATIONS_REQUIRING_CITATION:
        if len({origin_key(r.source) for r in cited}) < 2:
            add(
                CriticCheck.SOURCE_QUALITY,
                FindingSeverity.MEDIUM,
                "determination rests on a single independent origin",
                [str(r.evidence.id) for r in cited],
            )
        if cited and all(
            AuthorityLevel(r.components["authority_level"]) in LOW_AUTHORITY for r in cited
        ):
            add(
                CriticCheck.SOURCE_QUALITY,
                FindingSeverity.MEDIUM,
                "all cited origins are unassessed or of limited authority",
                [str(r.evidence.id) for r in cited],
            )
        best = max((r.score for r in cited), default=0.0)
        if assessment.confidence > 0.7 and best < 0.4:
            add(
                CriticCheck.UNSUPPORTED_CONCLUSIONS,
                FindingSeverity.HIGH,
                f"confidence {assessment.confidence} but best cited rank score is {best:.2f}",
                [],
            )
    return findings


def critique_assessment(
    ctx: PipelineContext, assessment: Assessment, pipeline_job_id: uuid.UUID | None
) -> Critique:
    session = ctx.session
    if assessment.produced_by != ProducedBy.AGENT or assessment.ai_run_id is None:
        raise ValueError("Only agent-produced assessments are critiqued.")
    assessor_run = session.get(AIRun, assessment.ai_run_id)
    if assessor_run is None or assessor_run.agent_name == FACT_CHECK_CRITIC.name:
        raise SelfReviewError("The critic cannot review an assessment it produced.")
    assert assessor_run.agent_name == ASSESSOR.name

    claim = session.get(Claim, assessment.claim_id)
    ranked = rank_claim_evidence(session, claim)
    labels = label_evidence(ranked)
    id_to_label = {r.evidence.id: label for label, r in labels.items()}
    cited_ids = set(
        session.scalars(
            select(AssessmentCitation.evidence_id).where(
                AssessmentCitation.assessment_id == assessment.id
            )
        )
    )
    cited = [r for r in labels.values() if r.evidence.id in cited_ids]
    ref = reference_date(claim)
    findings = deterministic_findings(assessment, cited, list(labels.values()), ref)
    findings_for_prompt = [
        {**f, "evidence": [id_to_label.get(uuid.UUID(e), e) for e in f["evidence"]]}
        for f in findings
    ]
    proposal_view = {
        "classification": assessment.classification.value,
        "confidence": assessment.confidence,
        "summary": assessment.summary,
        "reasoning": assessment.reasoning,
        "cited_evidence": [id_to_label[i] for i in cited_ids if i in id_to_label],
        "missing_information": assessment.missing_information,
    }
    required = {c for c in CriticCheck}

    def validate(p: CritiqueProposal) -> None:
        got = [c.check for c in p.checks]
        if set(got) != required or len(got) != len(required):
            missing = sorted(c.value for c in required - set(got))
            raise InvalidAgentOutput(f"report every check exactly once; missing={missing}")
        if p.outcome == CriticOutcome.PASS and not all(c.passed for c in p.checks):
            raise InvalidAgentOutput("outcome PASS is only allowed when every check passed")
        unknown = sorted({e for c in p.checks for e in c.evidence} - labels.keys())
        if unknown:
            raise InvalidAgentOutput(f"unknown evidence labels {unknown}")

    result = run_agent(
        session,
        ctx.critic_llm,
        FACT_CHECK_CRITIC,
        {
            "claim": claim.normalized_text,
            "time_reference": claim.time_reference or "not stated",
            "location": claim.location or "not stated",
            "assessment": json.dumps(proposal_view, indent=2, ensure_ascii=False),
            "evidence": render_evidence(labels) or "(none)",
            "findings": json.dumps(findings_for_prompt, indent=2, ensure_ascii=False)
            if findings
            else "(none)",
        },
        validate=validate,
        pipeline_job_id=pipeline_job_id,
    )
    p = result.output
    outcome = p.outcome
    overridden = False
    if outcome == CriticOutcome.PASS and any(
        f["severity"] == FindingSeverity.HIGH.value for f in findings
    ):
        outcome = CriticOutcome.ESCALATE
        overridden = True

    critique = Critique(
        assessment_id=assessment.id,
        outcome=outcome,
        agent_outcome=p.outcome,
        outcome_overridden=overridden,
        checks=[
            {
                **c.model_dump(mode="json"),
                "evidence": [str(labels[e].evidence.id) for e in c.evidence],
            }
            for c in p.checks
        ],
        deterministic_findings=findings,
        counter_argument=p.counter_argument,
        suggested_classification=p.suggested_classification,
        summary=p.summary,
        ai_run_id=result.ai_run.id,
    )
    session.add(critique)
    assessment.status = AssessmentStatus.CRITIQUED
    session.flush()
    AuditService(session).record(
        actor_type=ActorType.AGENT,
        actor_id=FACT_CHECK_CRITIC.name,
        action="critique.created",
        entity_type="critique",
        entity_id=critique.id,
        payload={
            "assessment_id": str(assessment.id),
            "outcome": outcome.value,
            "agent_outcome": p.outcome.value,
            "outcome_overridden": overridden,
            "failed_checks": [c.check.value for c in p.checks if not c.passed],
            "deterministic_findings": [f["check"] for f in findings],
            "suggested_classification": p.suggested_classification.value
            if p.suggested_classification
            else None,
            "ai_run_id": str(result.ai_run.id),
        },
    )
    return critique
