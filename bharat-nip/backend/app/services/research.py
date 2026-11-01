"""Evidence retrieval (FR-4): search -> snapshot sources -> select passages ->
evidence analyst proposes verbatim quotes -> mechanical quote verification -> evidence.

Every search, result, fetch, source and evidence decision is recorded and audited.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.definitions import EVIDENCE_ANALYST, EvidenceAnalysisOutput
from app.agents.runner import InvalidAgentOutput, run_agent
from app.ai.prompts import wrap_untrusted
from app.audit.service import AuditService
from app.domain.enums import ActorType, FetchStatus, SearchStatus, Stance
from app.domain.text import lexical_relevance, locate_quote, strip_placeholders
from app.ingest.extract import extract_document
from app.ingest.fetcher import FetchError
from app.models import (
    Claim,
    Evidence,
    SearchQuery,
    SearchResult,
    Source,
    SourceChunk,
    Submission,
)
from app.pipeline.context import PipelineContext
from app.providers.search.base import SearchError, SearchHit
from app.providers.search.mock import MockSearchNotScripted
from app.services.errors import Unprocessable
from app.services.registry import normalize_domain
from app.services.sources import store_source

_REPORTING_VERB = re.compile(
    r"^(?:said|says|claimed|claims|stated|states|announced|alleged|added)(?:\s+that)?\s+",
    re.IGNORECASE,
)


def claim_search_text(claim: Claim) -> str:
    """The text that relevance is measured against: blinded claim plus its triple."""
    return " ".join(
        x for x in [claim.normalized_text, claim.subject, claim.object_, claim.time_reference] if x
    )


def build_queries(claim: Claim) -> list[str]:
    """Deterministic queries from the blinded claim. Speaker identity never enters search."""
    q1 = " ".join(strip_placeholders(claim.normalized_text).split())
    q1 = _REPORTING_VERB.sub("", q1)
    q2 = " ".join(
        x
        for x in [claim.subject, claim.predicate, claim.object_, claim.location]
        if x and "[" not in x
    )
    q2 = " ".join(strip_placeholders(q2).split())
    queries = [q for q in [q1, q2] if q]
    return list(dict.fromkeys(queries))  # dedupe, keep order


def search_sources(
    ctx: PipelineContext, claim: Claim, pipeline_job_id: uuid.UUID | None
) -> list[Source]:
    """Pipeline stage SEARCH: run every configured provider for every query, snapshot
    the documents found, and record everything. Returns the distinct sources."""
    session = ctx.session
    submission = session.get(Submission, claim.submission_id)
    origin_domain = normalize_domain(submission.source_url) if submission else None
    origin_url = submission.source_url if submission else None
    sources: dict[uuid.UUID, Source] = {}

    for provider in ctx.search_providers:
        for query in build_queries(claim):
            sq = SearchQuery(
                claim_id=claim.id,
                provider=provider.name,
                query_text=query,
                status=SearchStatus.SUCCEEDED,
                executed_at=datetime.now(UTC),
                pipeline_job_id=pipeline_job_id,
            )
            try:
                hits = provider.search(
                    query, ctx.settings.search_results_per_query, session=session
                )
            except (SearchError, MockSearchNotScripted) as exc:
                hits = []
                sq.status = SearchStatus.FAILED
                sq.error = str(exc)[:2000]
            sq.result_count = len(hits)
            session.add(sq)
            session.flush()
            for rank, hit in enumerate(hits, start=1):
                src = _resolve_hit(ctx, sq, rank, hit, origin_url, origin_domain)
                if src is not None:
                    sources[src.id] = src
            AuditService(session).record(
                actor_type=ActorType.SYSTEM,
                actor_id=f"system:search:{provider.name}",
                action="search.executed",
                entity_type="claim",
                entity_id=claim.id,
                payload={
                    "search_query_id": str(sq.id),
                    "provider": provider.name,
                    "is_mock": provider.is_mock,
                    "query": query,
                    "status": sq.status.value,
                    "result_count": sq.result_count,
                    "error": sq.error,
                },
            )
    return list(sources.values())


def _resolve_hit(
    ctx: PipelineContext,
    sq: SearchQuery,
    rank: int,
    hit: SearchHit,
    origin_url: str | None,
    origin_domain: str | None,
) -> Source | None:
    session = ctx.session
    result = SearchResult(
        search_query_id=sq.id,
        rank=rank,
        url=hit.url,
        title=hit.title[:1000],
        snippet=hit.snippet,
        provider_score=hit.score,
        fetch_status=FetchStatus.SKIPPED,
    )
    source: Source | None = None
    try:
        if hit.url and origin_url and hit.url.rstrip("/") == origin_url.rstrip("/"):
            # The material the claim came from is not independent evidence about it.
            result.fetch_error = "original source of the claim; not independent evidence"
        elif hit.source_id is not None:
            source = session.get(Source, hit.source_id)
            result.fetch_status = FetchStatus.REUSED
        elif hit.content:
            source, created = store_source(
                session,
                title=hit.title,
                content_text=hit.content,
                url=hit.url,
                publisher_name=hit.publisher,
                published_at=hit.published_at,
                source_type=hit.source_type,
                language="en",
                retrieval_provider=sq.provider,
                fetch_metadata={"provided_by": sq.provider},
            )
            result.fetch_status = FetchStatus.PROVIDED if created else FetchStatus.REUSED
        elif hit.url:
            source, created = _fetch_and_store(ctx, sq.provider, hit)
            result.fetch_status = FetchStatus.FETCHED if created else FetchStatus.REUSED
    except (FetchError, Unprocessable, ValueError) as exc:
        result.fetch_status = FetchStatus.FAILED
        result.fetch_error = str(exc)[:2000]
        source = None
    result.source_id = source.id if source else None
    session.add(result)
    session.flush()
    return source


def _fetch_and_store(ctx: PipelineContext, provider: str, hit: SearchHit) -> tuple[Source, bool]:
    assert hit.url
    doc = ctx.fetcher.fetch(hit.url)
    extracted = extract_document(doc.content_type, doc.body)
    if extracted is None or not extracted.text:
        raise Unprocessable(f"No extractable text ({doc.content_type}).")
    return store_source(
        ctx.session,
        title=extracted.title or hit.title,
        content_text=extracted.text,
        url=doc.final_url,
        publisher_name=extracted.publisher or hit.publisher,
        published_at=extracted.published_at or hit.published_at,
        source_type=hit.source_type,
        language=extracted.language or "en",
        retrieval_provider=provider,
        fetch_metadata={
            "requested_url": doc.requested_url,
            "final_url": doc.final_url,
            "status_code": doc.status_code,
            "content_type": doc.content_type,
            "fetched_at": doc.fetched_at.isoformat(),
            "redirects": doc.redirects,
        },
    )


def analyse_evidence(
    ctx: PipelineContext,
    claim: Claim,
    sources: list[Source],
    pipeline_job_id: uuid.UUID | None,
) -> tuple[int, int]:
    session: Session = ctx.session
    if not sources:
        return 0, 0
    claim_text = claim_search_text(claim)
    chunks = session.scalars(
        select(SourceChunk)
        .where(SourceChunk.source_id.in_([s.id for s in sources]))
        .order_by(SourceChunk.source_id, SourceChunk.chunk_index)
    ).all()
    scored = sorted(
        ((lexical_relevance(claim_text, c.text), c) for c in chunks),
        key=lambda x: (-x[0], str(x[1].source_id), x[1].chunk_index),
    )
    selected = [(s, c) for s, c in scored if s > 0][: ctx.settings.max_evidence_chunks]
    if not selected:
        return 0, 0
    by_source = {s.id: s for s in sources}
    labels = {f"C{i}": (score, chunk) for i, (score, chunk) in enumerate(selected, start=1)}
    passages = "\n\n".join(
        wrap_untrusted(
            "PASSAGE",
            label,
            f"Title: {by_source[chunk.source_id].title}\n"
            f"Publisher: {by_source[chunk.source_id].publisher_name or 'unknown'}\n"
            f"Published: {_fmt_date(by_source[chunk.source_id].published_at)}\n\n{chunk.text}",
        )
        for label, (_, chunk) in labels.items()
    )

    def validate(output: EvidenceAnalysisOutput) -> None:
        unknown = sorted({i.chunk for i in output.items} - labels.keys())
        if unknown:
            raise InvalidAgentOutput(f"Unknown passage labels: {unknown}")

    result = run_agent(
        session,
        ctx.llm,
        EVIDENCE_ANALYST,
        {
            "claim": claim.normalized_text,
            "time_reference": claim.time_reference or "not stated",
            "location": claim.location or "not stated",
            "passages": passages,
        },
        validate=validate,
        pipeline_job_id=pipeline_job_id,
    )

    audit = AuditService(session)
    created = rejected = 0
    existing = {
        (e.source_id, e.quote_char_start, e.quote_char_end)
        for e in session.scalars(select(Evidence).where(Evidence.claim_id == claim.id))
    }
    for item in result.output.items:
        lexical, chunk = labels[item.chunk]
        source = by_source[chunk.source_id]
        reason = None
        span = locate_quote(chunk.text, item.quote)
        if item.stance == Stance.NOT_RELEVANT:
            reason = "marked NOT_RELEVANT"
        elif span is None:
            reason = "quote not found verbatim in the passage"
        else:
            start, end = chunk.char_start + span[0], chunk.char_start + span[1]
            if (source.id, start, end) in existing:
                reason = "duplicate of existing evidence"
        if reason:
            rejected += 1
            audit.record(
                actor_type=ActorType.SYSTEM,
                actor_id="system:evidence_guardrail",
                action="evidence.rejected",
                entity_type="claim",
                entity_id=claim.id,
                payload={
                    "reason": reason,
                    "passage": item.chunk,
                    "source_id": str(source.id),
                    "proposed_quote": item.quote[:500],
                    "stance": item.stance.value,
                    "ai_run_id": str(result.ai_run.id),
                },
            )
            continue
        existing.add((source.id, start, end))
        quote = source.content_text[start:end]  # the stored text, not the model's copy
        quote_lexical = max(lexical_relevance(claim_text, quote), lexical)
        evidence = Evidence(
            claim_id=claim.id,
            source_id=source.id,
            chunk_id=chunk.id,
            quote=quote,
            quote_char_start=start,
            quote_char_end=end,
            stance=item.stance,
            stance_rationale=item.rationale,
            directness=item.directness,
            lexical_relevance=round(quote_lexical, 4),
            agent_relevance=item.relevance,
            relevance=round((quote_lexical + item.relevance) / 2, 4),
            extracted_by_ai_run_id=result.ai_run.id,
        )
        session.add(evidence)
        session.flush()
        created += 1
        audit.record(
            actor_type=ActorType.AGENT,
            actor_id=EVIDENCE_ANALYST.name,
            action="evidence.created",
            entity_type="evidence",
            entity_id=evidence.id,
            payload={
                "claim_id": str(claim.id),
                "source_id": str(source.id),
                "url": source.url,
                "content_sha256": source.content_sha256,
                "quote_char_start": start,
                "quote_char_end": end,
                "stance": item.stance.value,
                "directness": item.directness.value,
                "relevance": evidence.relevance,
                "ai_run_id": str(result.ai_run.id),
            },
        )
    return created, rejected


def _fmt_date(d: datetime | None) -> str:
    return d.date().isoformat() if d else "unknown"
