"""Agent implementations. Deterministic agents use tools only; LLM agents use versioned
prompts through the shared agent runner (every call is an ai_run). No handler can call another
agent: inputs come only from the task input and upstream step outputs, wired by the workflow.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from app.agents.runner import AgentFailed, AgentSpec, InputTooLarge, InvalidAgentOutput, run_agent
from app.ai.prompts import wrap_untrusted
from app.org import compliance
from app.org import schemas as S
from app.org.agents import AgentDefinition
from app.org.policy import (
    AI_ASSISTED_LABEL,
    MACHINE_TRANSLATION_NOTE,
    ORG_VERSION,
    SUPPORTED_LANGUAGES,
    InvalidAgentOutputError,
    ModelRole,
    NoApprovedEvidence,
    OrgError,
    TokenLimitExceeded,
)
from app.org.tools import ToolContext


@dataclass
class HandlerResult:
    output: BaseModel
    ai_run_ids: list[uuid.UUID] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str | None = None


Handler = Callable[[ToolContext, BaseModel, dict[str, Any], list[dict]], HandlerResult]
HANDLERS: dict[str, Handler] = {}


def handler(key: str):
    def register(fn: Handler) -> Handler:
        HANDLERS[key] = fn
        return fn

    return register


def feedback_block(feedback: list[dict]) -> str:
    if not feedback:
        return ""
    return "\nREVISION REQUESTED. Address every point below:\n" + json.dumps(
        feedback[-3:], ensure_ascii=False, indent=1
    )


def llm_call(
    tc: ToolContext,
    agent: AgentDefinition,
    prompt_id: str,
    model: type[BaseModel],
    variables: dict[str, str],
    validate=None,
) -> HandlerResult:
    provider = tc.pipeline.critic_llm if agent.model == ModelRole.CRITIC else tc.pipeline.llm
    spec = AgentSpec(
        name=agent.key,
        version=ORG_VERSION,
        prompt_id=prompt_id,
        prompt_version="v1",
        output_model=model,
        max_tokens=agent.max_output_tokens,
    )
    try:
        result = run_agent(
            tc.session,
            provider,
            spec,
            variables,
            validate=validate,
            max_input_tokens=agent.max_input_tokens,
            max_output_tokens=agent.max_output_tokens,
        )
    except InputTooLarge as exc:
        raise TokenLimitExceeded(str(exc)) from exc
    except AgentFailed as exc:
        if "no valid output" in exc.detail:
            raise InvalidAgentOutputError(exc.detail) from exc
        raise OrgError(exc.detail) from exc
    run = result.ai_run
    return HandlerResult(
        output=result.output,
        ai_run_ids=[run.id],
        prompt_tokens=run.prompt_tokens or 0,
        completion_tokens=run.completion_tokens or 0,
        model=f"{run.provider}/{run.model}",
    )


# --- research desk -----------------------------------------------------------------------


@handler("claim_extraction_agent")
def claim_extraction(tc, inp: S.SubmissionTaskInput, upstream, feedback) -> HandlerResult:
    return HandlerResult(
        S.ExtractionOutput(**tc.call("extract_submission", submission_id=inp.submission_id))
    )


@handler("research_agent")
def research(tc, inp: S.ResearchInput, upstream, feedback) -> HandlerResult:
    claims = []
    for cid in inp.claim_ids:
        status = tc.call("run_claim_pipeline", claim_id=cid)
        r = tc.call("read_claim_research", claim_id=cid)
        stances = Counter(e["stance"] for e in r["evidence"])
        claims.append(
            {
                "claim_id": str(cid),
                "status": status,
                "searches": r["searches"],
                "sources": len({e["source_id"] for e in r["evidence"]}),
                "evidence_by_stance": dict(stances),
                "top_evidence": [
                    {k: e[k] for k in ("evidence_id", "source_title", "stance", "rank_score")}
                    for e in r["evidence"][:3]
                ],
            }
        )
    return HandlerResult(S.ResearchOutput(claims=claims))


@handler("source_verification_agent")
def source_verification(tc, inp: S.ClaimTaskInput, upstream, feedback) -> HandlerResult:
    r = tc.call("read_claim_research", claim_id=inp.claim_id)
    sources: dict[str, dict] = {}
    for e in r["evidence"]:
        if e["source_id"] in sources:
            continue
        reg = tc.call("read_registry", source_id=uuid.UUID(e["source_id"]), claim_text=r["claim"])
        flags = []
        if not reg["registered"]:
            flags.append("unregistered_origin")
        if reg["effective_authority"] in ("UNASSESSED", "LIMITED"):
            flags.append("low_or_unassessed_authority")
        if e["age_years"] is not None and e["age_years"] > 5:
            flags.append("outdated")
        if e["quality"] < 0.5:
            flags.append("low_document_quality")
        sources[e["source_id"]] = {
            "source_id": e["source_id"],
            "title": e["source_title"],
            "publisher": e["publisher"],
            "is_primary": e["is_primary"],
            "age_years": e["age_years"],
            "document_quality": e["quality"],
            **reg,
            "flags": flags,
        }
    summary = []
    if not sources:
        summary.append("no_sources")
    if sources and len({s["registry_name"] or s["publisher"] for s in sources.values()}) < 2:
        summary.append("single_origin")
    if sources and not any(s["is_primary"] for s in sources.values()):
        summary.append("no_primary_source")
    if sources and all("low_or_unassessed_authority" in s["flags"] for s in sources.values()):
        summary.append("only_low_authority_sources")
    return HandlerResult(
        S.SourceVerificationOutput(sources=list(sources.values()), summary_flags=summary)
    )


@handler("media_forensics_agent")
def media_forensics(tc, inp: S.SubmissionTaskInput, upstream, feedback) -> HandlerResult:
    m = tc.call("read_media", submission_id=inp.submission_id)
    findings = []
    if m["file"] is None:
        findings.append("The submission has no uploaded file.")
    else:
        f = m["file"]
        findings.append(f"{f['content_type']}, {f['size_bytes']} bytes, sha256 {f['sha256'][:16]}…")
        if m["reuse"]:
            findings.append(
                f"Identical file was submitted {len(m['reuse'])} other time(s); earliest "
                f"{m['reuse'][0]['submitted_at'][:10]}. Recycled media can be a sign of "
                "out-of-context use."
            )
        if f.get("has_exif") is False or f.get("has_text_metadata_chunks") is False:
            findings.append(
                "No embedded metadata found (common after re-sharing; not evidence "
                "of manipulation by itself)."
            )
    limitations = [
        "No manipulation, editing or deepfake detection is performed.",
        "No reverse image search is available.",
        "Absence or presence of metadata proves nothing on its own.",
    ]
    return HandlerResult(
        S.MediaForensicsOutput(
            file=m["file"], reuse=m["reuse"], findings=findings, limitations=limitations
        )
    )


# --- verification desk -------------------------------------------------------------------


@handler("fact_check_agent")
def fact_check(tc, inp: S.FactCheckInput, upstream, feedback) -> HandlerResult:
    claims = [tc.call("read_fact_check", claim_id=c) for c in inp.claim_ids]
    pending = sum(1 for c in claims if c["review_status"] in ("PENDING_REVIEW", "NOT_READY"))
    return HandlerResult(S.FactCheckOutput(claims=claims, pending_human_review=pending))


def _evidence_labels(research: dict) -> tuple[str, dict[str, dict]]:
    usable = [e for e in research["evidence"] if e["stance"] != "NOT_RELEVANT"][:12]
    labels = {f"E{i}": e for i, e in enumerate(usable, start=1)}
    text = "\n\n".join(
        wrap_untrusted(
            "EVIDENCE",
            k,
            f"Stance: {e['stance']} | Source: {e['source_title']} "
            f"({e['publisher'] or 'unknown'})\nQuote: {e['quote']}",
        )
        for k, e in labels.items()
    )
    return text or "(no evidence)", labels


@handler("context_agent")
def context(tc, inp: S.ClaimTaskInput, upstream, feedback) -> HandlerResult:
    r = tc.call("read_claim_research", claim_id=inp.claim_id)
    evidence, labels = _evidence_labels(r)
    if not labels:
        raise NoApprovedEvidence("The claim has no evidence to ground context in.")

    def validate(out: S.ContextOutput) -> None:
        for p in out.context_points:
            bad = [c for c in p.citations if c not in labels]
            if not p.citations or bad:
                raise InvalidAgentOutput(f"context point needs valid citations; bad={bad}")

    return llm_call(
        tc,
        tc.agent,
        "context_agent",
        S.ContextOutput,
        {"claim": r["claim"], "evidence": evidence, "feedback": feedback_block(feedback)},
        validate,
    )


# --- narrative / analytics ---------------------------------------------------------------


@handler("narrative_intelligence_agent")
def narrative(tc, inp: S.NarrativeResponseInput, upstream, feedback) -> HandlerResult:
    tc.call("run_narrative_engine")
    n = tc.call("read_narrative", narrative_id=inp.narrative_id)
    m = n["metrics"]
    if m is None:
        raise OrgError("The narrative has no metrics yet.")
    facts = tc.call("read_approved_facts", narrative_id=inp.narrative_id)
    return HandlerResult(
        S.NarrativeBrief(
            narrative_id=n["narrative_id"],
            title=n["title"],
            status=n["status"],
            recommendation=m["recommendation"],
            rule=m["details"]["recommendation"]["rule"],
            rationale=m["details"]["recommendation"]["rationale"],
            evidence_status=m["evidence_status"],
            momentum=m["momentum"],
            public_interest=m["public_interest"],
            harm_severity=n["harm_severity"],
            coverage=m["coverage"],
            facts=facts,
        )
    )


@handler("analytics_agent")
def analytics(tc, inp: S.AnalyticsTaskInput, upstream, feedback) -> HandlerResult:
    return HandlerResult(
        S.AnalyticsOutput(**tc.call("read_analytics", window_days=inp.window_days))
    )


# --- communications desk -----------------------------------------------------------------


def facts_block(facts: list[dict]) -> str:
    return (
        "\n\n".join(
            wrap_untrusted(
                "FACT",
                f["label"],
                f"Claim: {f['claim']}\nApproved classification: "
                f"{f['approved_classification']}\nSummary: {f['summary']}\n"
                + "\n".join(f"Quote: {q}" for q in f["quotes"]),
            )
            for f in facts
        )
        or "(no approved fact-checks)"
    )


def _check_citations(sentences: list[S.CitedSentence], labels: set[str], what: str) -> None:
    for i, s in enumerate(sentences, start=1):
        bad = [c for c in s.citations if c not in labels]
        if not s.citations or bad:
            raise InvalidAgentOutput(f"{what} {i} needs valid fact citations; bad={bad}")


# Public content is drafted only when the engine recommends correcting or responding.
FORMATS_FOR_POSTURE = {
    "CORRECT": {"CORRECTION"},
    "RESPOND": {"EXPLAINER", "CONTEXT_NOTE"},
}


@handler("response_strategist")
def strategist(tc, inp: S.NarrativeBrief, upstream, feedback) -> HandlerResult:
    labels = {f["label"] for f in inp.facts}

    def validate(out: S.StrategyOutput) -> None:
        if out.posture != inp.recommendation:
            raise InvalidAgentOutput(
                f"posture must equal the engine recommendation {inp.recommendation.value}"
            )
        allowed = FORMATS_FOR_POSTURE.get(out.posture.value, {"NONE"})
        if out.format not in allowed:
            raise InvalidAgentOutput(
                f"format for posture {out.posture.value} must be one of {sorted(allowed)}"
            )
        if out.format != "NONE":
            _check_citations(out.key_messages, labels, "key message")

    return llm_call(
        tc,
        tc.agent,
        "response_strategist",
        S.StrategyOutput,
        {
            "title": inp.title,
            "recommendation": inp.recommendation.value,
            "rule": inp.rule,
            "rationale": inp.rationale,
            "evidence_status": inp.evidence_status,
            "momentum": f"{inp.momentum:.2f}",
            "public_interest": f"{inp.public_interest:.2f}",
            "harm": inp.harm_severity,
            "coverage": f"{inp.coverage:.2f}",
            "facts": facts_block(inp.facts),
            "feedback": feedback_block(feedback),
        },
        validate,
    )


@handler("content_agent")
def content(tc, inp: S.StrategyOutput, upstream, feedback) -> HandlerResult:
    facts = upstream["narrative"]["facts"]
    if not facts:
        raise NoApprovedEvidence("No human-approved fact-check exists for this narrative.")
    labels = {f["label"] for f in facts}
    known = compliance.fact_texts(facts)

    def validate(out: S.ContentDraft) -> None:
        _check_citations(out.sentences, labels, "sentence")
        for i, s in enumerate(out.sentences, start=1):
            extra = compliance.ungrounded_numbers(s, known)
            if extra:
                raise InvalidAgentOutput(
                    f"sentence {i} uses numbers {sorted(extra)} not found in cited facts"
                )
        if out.ai_assisted_label != AI_ASSISTED_LABEL:
            raise InvalidAgentOutput("ai_assisted_label must be exactly the required label")

    return llm_call(
        tc,
        tc.agent,
        "content_agent",
        S.ContentDraft,
        {
            "label": AI_ASSISTED_LABEL,
            "format": inp.format,
            "objectives": "; ".join(inp.objectives),
            "key_messages": json.dumps([m.model_dump() for m in inp.key_messages]),
            "do_not": "; ".join(inp.do_not),
            "facts": facts_block(facts),
            "feedback": feedback_block(feedback),
        },
        validate,
    )


@handler("localization_agent")
def localization(tc, inp: S.ContentDraft, upstream, feedback) -> HandlerResult:
    languages = upstream["_task"].get("languages", [])
    out: list[S.Translation] = []
    total = HandlerResult(output=S.LocalizationOutput(translations=[], note=""))
    for lang in languages:

        def validate(t: S.Translation, lang=lang) -> None:
            if t.language != lang:
                raise InvalidAgentOutput(f"language must be {lang}")
            if len(t.sentences) != len(inp.sentences):
                raise InvalidAgentOutput("translate every sentence, one for one")
            for i, (a, b) in enumerate(zip(inp.sentences, t.sentences, strict=True), 1):
                if sorted(a.citations) != sorted(b.citations):
                    raise InvalidAgentOutput(f"sentence {i}: keep the citations unchanged")
                if compliance.numbers(a.text) != compliance.numbers(b.text):
                    raise InvalidAgentOutput(f"sentence {i}: keep every number unchanged")

        r = llm_call(
            tc,
            tc.agent,
            "localization_agent",
            S.Translation,
            {
                "language": lang,
                "language_name": SUPPORTED_LANGUAGES[lang],
                "draft": json.dumps(inp.model_dump(), ensure_ascii=False),
                "feedback": feedback_block(feedback),
            },
            validate,
        )
        out.append(r.output)
        total.ai_run_ids += r.ai_run_ids
        total.prompt_tokens += r.prompt_tokens
        total.completion_tokens += r.completion_tokens
        total.model = r.model
    total.output = S.LocalizationOutput(translations=out, note=MACHINE_TRANSLATION_NOTE)
    return total


@handler("compliance_agent")
def compliance_gate(tc, inp: S.ContentDraft, upstream, feedback) -> HandlerResult:
    translations = [
        S.Translation(**t) for t in (upstream.get("localization") or {}).get("translations", [])
    ]
    return HandlerResult(compliance.check(inp, translations, upstream["narrative"]["facts"]))


@handler("critic_agent")
def critic_review(tc, inp: S.ChiefInput, upstream, feedback) -> HandlerResult:
    """Called by the engine as a reviewer; `inp.input` carries agent, materials and output."""

    def validate(c: S.OrgCritique) -> None:
        if c.verdict == "PASS" and any(i.severity in ("MEDIUM", "HIGH") for i in c.issues):
            raise InvalidAgentOutput("PASS is only allowed without MEDIUM or HIGH issues")
        if c.verdict == "REVISE" and not c.issues:
            raise InvalidAgentOutput("REVISE needs at least one specific issue")

    return llm_call(
        tc,
        tc.agent,
        "org_critic",
        S.OrgCritique,
        {
            "agent": inp.input["agent"],
            "task": inp.title,
            "materials": json.dumps(inp.input["materials"], ensure_ascii=False, default=str)[
                :20000
            ],
            "output": json.dumps(inp.input["output"], ensure_ascii=False, default=str),
        },
        validate,
    )
