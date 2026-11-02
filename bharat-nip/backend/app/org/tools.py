"""Permissioned tools. An agent can call a tool only if it is on the agent's allowlist and the
agent holds the tool's permission. Every call is logged on the execution record.

There is deliberately no tool that publishes, sends, posts, schedules or contacts anyone.
"""

from __future__ import annotations

import time
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import (
    ClaimStatus,
    ReviewTaskStatus,
    Stance,
)
from app.domain.state import review_status_for
from app.models import (
    AIRun,
    Claim,
    Narrative,
    NarrativeMetric,
    OrgExecution,
    RegistrySource,
    ReviewTask,
    SearchQuery,
    Source,
    StoredFile,
    Submission,
)
from app.narratives.engine import approved_verifications, display_text, run_engine
from app.narratives.queries import latest_metrics, member_claim_ids, metrics_dict
from app.org.agents import AgentDefinition
from app.org.policy import OrgError, Permission, PermissionDenied
from app.pipeline import orchestrator
from app.pipeline.context import PipelineContext
from app.services.factcheck import build_fact_check, latest_assessment
from app.services.ranking import evidence_age_years, rank_claim_evidence, reference_date
from app.services.registry import effective_authority
from app.services.storage import read_stored


@dataclass
class ToolContext:
    session: Session
    pipeline: PipelineContext
    agent: AgentDefinition
    calls: list[dict[str, Any]] = field(default_factory=list)

    def call(self, name: str, **kwargs: Any) -> Any:
        tool = TOOLS.get(name)
        record: dict[str, Any] = {
            "tool": name,
            "args": {k: str(v) for k, v in kwargs.items()},
        }
        started = time.monotonic()
        try:
            if tool is None or name not in self.agent.tools:
                raise PermissionDenied(f"{self.agent.key} may not use tool {name!r}")
            permission, fn = tool
            if permission not in self.agent.permissions:
                raise PermissionDenied(f"{self.agent.key} lacks permission {permission.value}")
            result = fn(self, **kwargs)
            record["ok"] = True
            return result
        except OrgError as exc:
            record["ok"] = False
            record["error"] = exc.detail
            raise
        except Exception as exc:
            record["ok"] = False
            record["error"] = f"{type(exc).__name__}: {exc}"
            raise OrgError(f"tool {name} failed: {exc}") from exc
        finally:
            record["ms"] = int((time.monotonic() - started) * 1000)
            self.calls.append(record)


ToolFn = Callable[..., Any]
TOOLS: dict[str, tuple[Permission, ToolFn]] = {}


def tool(name: str, permission: Permission):
    def register(fn: ToolFn) -> ToolFn:
        TOOLS[name] = (permission, fn)
        return fn

    return register


def _claim(session: Session, claim_id: uuid.UUID) -> Claim:
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise OrgError(f"claim {claim_id} not found")
    return claim


# --- pipeline ----------------------------------------------------------------------------


@tool("extract_submission", Permission.RUN_PIPELINE)
def extract_submission(tc: ToolContext, submission_id: uuid.UUID) -> dict[str, Any]:
    sub = tc.session.get(Submission, submission_id)
    if sub is None:
        raise OrgError(f"submission {submission_id} not found")
    existing = list(tc.session.scalars(select(Claim).where(Claim.submission_id == sub.id)))
    if not existing and sub.status.value in ("RECEIVED", "PROCESSING"):
        orchestrator.extract_submission(tc.pipeline, sub.id)
        tc.session.refresh(sub)
        existing = list(tc.session.scalars(select(Claim).where(Claim.submission_id == sub.id)))
    return {
        "submission_status": sub.status.value,
        "extraction_method": sub.extraction_method.value if sub.extraction_method else None,
        "extraction_notes": sub.extraction_notes,
        "claims": [
            {
                "claim_id": str(c.id),
                "text": display_text(c.normalized_text),
                "claim_type": c.claim_type.value,
                "status": c.status.value,
            }
            for c in existing
        ],
    }


@tool("run_claim_pipeline", Permission.RUN_PIPELINE)
def run_claim_pipeline(tc: ToolContext, claim_id: uuid.UUID) -> str:
    claim = _claim(tc.session, claim_id)
    if claim.status in (ClaimStatus.EXTRACTED, ClaimStatus.NEEDS_MORE_RESEARCH):
        orchestrator.process_claim(tc.pipeline, claim.id)
        tc.session.refresh(claim)
    return claim.status.value


# --- reading -----------------------------------------------------------------------------


@tool("read_claim_research", Permission.READ_EVIDENCE)
def read_claim_research(tc: ToolContext, claim_id: uuid.UUID) -> dict[str, Any]:
    s = tc.session
    claim = _claim(s, claim_id)
    ranked = rank_claim_evidence(s, claim)
    searches = s.scalar(select(func.count()).where(SearchQuery.claim_id == claim.id)) or 0
    return {
        "claim_id": str(claim.id),
        "claim": claim.normalized_text,
        "status": claim.status.value,
        "searches": searches,
        "reference_date": reference_date(claim).isoformat(),
        "evidence": [
            {
                "evidence_id": str(r.evidence.id),
                "source_id": str(r.source.id),
                "stance": r.evidence.stance.value,
                "directness": r.evidence.directness.value,
                "quote": r.evidence.quote,
                "rank_score": r.score,
                "authority_level": r.components["authority_level"],
                "source_title": r.source.title,
                "publisher": r.source.publisher_name,
                "published_at": r.source.published_at.isoformat()
                if r.source.published_at
                else None,
                "is_primary": r.source.is_primary,
                "age_years": round(age, 2)
                if (age := evidence_age_years(r.source, reference_date(claim))) is not None
                else None,
                "quality": r.components["factors"]["document_quality"],
            }
            for r in ranked
        ],
    }


@tool("read_registry", Permission.READ_REGISTRY)
def read_registry(tc: ToolContext, source_id: uuid.UUID, claim_text: str) -> dict[str, Any]:
    src = tc.session.get(Source, source_id)
    if src is None:
        raise OrgError(f"source {source_id} not found")
    entry = (
        tc.session.get(RegistrySource, src.registry_source_id) if src.registry_source_id else None
    )
    auth = effective_authority(entry, claim_text)
    return {
        "registered": entry is not None,
        "registry_name": entry.name if entry else None,
        "category": entry.category.value if entry else None,
        "jurisdiction": entry.jurisdiction if entry else None,
        "verification_status": entry.verification_status.value if entry else None,
        "effective_authority": auth.level.value,
        "authority_basis": auth.basis,
    }


@tool("read_media", Permission.READ_MEDIA)
def read_media(tc: ToolContext, submission_id: uuid.UUID) -> dict[str, Any]:
    s = tc.session
    sub = s.get(Submission, submission_id)
    if sub is None:
        raise OrgError(f"submission {submission_id} not found")
    if sub.file_id is None:
        return {"file": None, "reuse": []}
    stored = s.get(StoredFile, sub.file_id)
    data = read_stored(tc.pipeline.settings, stored)
    props: dict[str, Any] = {
        "sha256": stored.sha256,
        "content_type": stored.content_type,
        "size_bytes": stored.size_bytes,
        "filename": stored.filename,
    }
    props.update(_media_properties(stored.content_type, data))
    reuse = [
        {"submission_id": str(other.id), "submitted_at": other.created_at.isoformat()}
        for other, f in s.execute(
            select(Submission, StoredFile)
            .join(StoredFile, StoredFile.id == Submission.file_id)
            .where(StoredFile.sha256 == stored.sha256, Submission.id != sub.id)
            .order_by(Submission.created_at)
        )
    ]
    return {"file": props, "reuse": reuse}


def _media_properties(content_type: str, data: bytes) -> dict[str, Any]:
    """Facts readable directly from the bytes. No interpretation."""
    out: dict[str, Any] = {}
    if content_type == "image/png" and len(data) >= 24:
        out["width"] = int.from_bytes(data[16:20], "big")
        out["height"] = int.from_bytes(data[20:24], "big")
        out["has_text_metadata_chunks"] = any(c in data for c in (b"tEXt", b"iTXt", b"zTXt"))
    elif content_type == "image/jpeg":
        out["has_exif"] = b"Exif\x00\x00" in data[:65536]
    elif content_type == "application/pdf":
        out["pdf_version"] = data[5:8].decode("latin-1", errors="replace")
        out["has_info_dictionary"] = b"/Info" in data
    return out


@tool("read_fact_check", Permission.READ_FACT_CHECKS)
def read_fact_check(tc: ToolContext, claim_id: uuid.UUID) -> dict[str, Any]:
    s = tc.session
    claim = _claim(s, claim_id)
    fc = build_fact_check(s, claim)
    approved = approved_verifications(s).get(claim.id)
    return {
        "claim_id": str(claim.id),
        "text": display_text(claim.normalized_text),
        "claim_status": claim.status.value,
        "review_status": review_status_for(claim.status).value,
        "latest_classification": fc["classification"] if fc else None,
        "latest_confidence": fc["confidence"] if fc else None,
        "critic_outcome": fc["critic"]["outcome"] if fc and fc["critic"] else None,
        "approved_classification": approved[0].value if approved else None,
        "summary": fc["summary"] if fc else None,
    }


@tool("run_narrative_engine", Permission.RUN_ANALYSIS)
def run_narrative_engine(tc: ToolContext) -> dict[str, Any]:
    return run_engine(tc.session).as_dict()


@tool("read_narrative", Permission.READ_NARRATIVES)
def read_narrative(tc: ToolContext, narrative_id: uuid.UUID) -> dict[str, Any]:
    n = tc.session.get(Narrative, narrative_id)
    if n is None:
        raise OrgError(f"narrative {narrative_id} not found")
    return {
        "narrative_id": str(n.id),
        "title": n.title,
        "status": n.status.value,
        "harm_severity": n.harm_severity.value,
        "metrics": metrics_dict(latest_metrics(tc.session, n.id)),
    }


@tool("read_approved_facts", Permission.READ_FACT_CHECKS)
def read_approved_facts(tc: ToolContext, narrative_id: uuid.UUID) -> list[dict[str, Any]]:
    """Human-approved fact-checks of the narrative's claims, labelled F1..Fn."""
    s = tc.session
    approved = approved_verifications(s)
    facts = []
    for cid in sorted(member_claim_ids(s, narrative_id), key=str):
        if cid not in approved:
            continue
        claim = s.get(Claim, cid)
        a = latest_assessment(s, cid)
        fc = build_fact_check(s, claim) or {}
        quotes = [e["quote"] for e in fc.get("supporting_evidence", [])[:2]] + [
            e["quote"] for e in fc.get("contradicting_evidence", [])[:2]
        ]
        facts.append(
            {
                "label": f"F{len(facts) + 1}",
                "claim_id": str(cid),
                "claim": display_text(claim.normalized_text),
                "approved_classification": approved[cid][0].value,
                "summary": a.summary if a else "",
                "quotes": quotes,
            }
        )
    return facts


@tool("read_analytics", Permission.READ_ANALYTICS)
def read_analytics(tc: ToolContext, window_days: int) -> dict[str, Any]:
    """Aggregate counts only. There is no individual-level data to read."""
    s = tc.session
    since = datetime.now(UTC) - timedelta(days=window_days)
    approved = approved_verifications(s)
    by_class = Counter(v[0].value for v in approved.values())
    backlog = s.scalar(select(func.count()).where(ReviewTask.status == ReviewTaskStatus.OPEN)) or 0
    recs: Counter[str] = Counter()
    trend = []
    for n in s.scalars(select(Narrative)):
        m = latest_metrics(s, n.id)
        if m:
            recs[m.recommendation.value] += 1
        snaps = s.scalars(
            select(NarrativeMetric)
            .where(NarrativeMetric.narrative_id == n.id, NarrativeMetric.computed_at >= since)
            .order_by(NarrativeMetric.version)
        ).all()
        if snaps:
            trend.append(
                {
                    "narrative_id": str(n.id),
                    "title": n.title,
                    "momentum_first": snaps[0].momentum,
                    "momentum_last": snaps[-1].momentum,
                    "claims_last": snaps[-1].claim_count,
                }
            )
    executions = Counter(
        s.scalars(select(OrgExecution.agent_key).where(OrgExecution.created_at >= since))
    )
    executions.update(s.scalars(select(AIRun.agent_name).where(AIRun.created_at >= since)))
    return {
        "window_days": window_days,
        "claims_by_classification": dict(by_class),
        "review_backlog": backlog,
        "narratives_by_recommendation": dict(recs),
        "narrative_trend": trend,
        "agent_executions": dict(executions),
    }


STANCES = [s.value for s in Stance]
