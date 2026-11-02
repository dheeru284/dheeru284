"""Fictional scenario helpers for organization tests (builds on tests/scenario.py)."""

from __future__ import annotations

import json
import re

from sqlalchemy import select

from app.domain.enums import (
    Classification,
    ObservationMetric,
    ReviewDecisionType,
    SubmissionType,
)
from app.models import Claim, NarrativeClaim, ReviewTask
from app.narratives import service as narrative_service
from app.narratives.engine import run_engine
from app.org.policy import AI_ASSISTED_LABEL
from app.pipeline import orchestrator
from app.services import review
from app.services.submissions import SubmissionInput, create_submission
from tests import scenario as sc

CHECKS = sc.CHECKS


def script_pipeline(world) -> None:
    world.llm.script("claim_extractor", sc.extraction_response(), reusable=True)
    world.search.script([sc.stats_hit(), sc.news_hit()])
    world.llm.script("evidence_analyst", sc.evidence_response, reusable=True)
    world.llm.script("assessor", sc.assessment_response("MOSTLY_TRUE", 0.8), reusable=True)
    world.llm.script("fact_check_critic", sc.critic_response("PASS"), reusable=True)


def submit(db, world, text=sc.SUBMISSION_TEXT):
    sub, _ = create_submission(
        db, world.submitter, SubmissionInput(submission_type=SubmissionType.TEXT, raw_text=text)
    )
    return sub


def correctable_narrative(db, ctx, world):
    """Two submissions of the claim, one fact-check approved (reviewer override to FALSE),
    plus aggregate public views => recommendation CORRECT."""
    script_pipeline(world)
    for _ in range(2):
        orchestrator.process_submission(ctx, submit(db, world).id)
    task = db.scalars(select(ReviewTask).where(ReviewTask.status == "OPEN")).first()
    review.decide(
        db,
        task.id,
        world.reviewer,
        ReviewDecisionType.APPROVE,
        Classification.FALSE,
        "Fictional reviewer override for the test.",
    )
    run_engine(db)
    claim = db.scalar(select(Claim).where(Claim.id == task.claim_id))
    nid = db.scalar(select(NarrativeClaim.narrative_id).where(NarrativeClaim.claim_id == claim.id))
    from datetime import UTC, datetime

    narrative_service.add_observation(
        db,
        world.submitter,
        nid,
        observed_at=datetime.now(UTC),
        channel="video-site",
        metric=ObservationMetric.VIEWS,
        value=500_000,
        source_url=None,
        note=None,
    )
    run_engine(db)
    return nid


def strategy(request):
    rec = re.search(r"Engine recommendation: (\w+)", request.messages[-1].content).group(1)
    fmt = {"CORRECT": "CORRECTION", "RESPOND": "EXPLAINER"}.get(rec, "NONE")
    return json.dumps(
        {
            "posture": rec,
            "objectives": ["Give people the official figure"],
            "key_messages": [
                {"text": "The official 2023 figure is 81.2 percent.", "citations": ["F1"]}
            ]
            if fmt != "NONE"
            else [],
            "channels": ["OFFICIAL_WEBSITE", "FACT_CHECK_PAGE"] if fmt != "NONE" else [],
            "format": fmt,
            "do_not": ["Do not repeat the inaccurate figure in the headline"],
        }
    )


def content(
    text="Official statistics put the state literacy rate at 81.2 percent in 2023.",
    label=AI_ASSISTED_LABEL,
):
    return json.dumps(
        {
            "format": "CORRECTION",
            "headline": "What the official literacy data shows",
            "sentences": [{"text": text, "citations": ["F1"]}],
            "ai_assisted_label": label,
        }
    )


def translation(request):
    lang = re.search(r'with `language` set to "(\w+)"', request.messages[0].content).group(1)
    draft = json.loads(re.search(r"Draft:\n(\{.*\})", request.messages[-1].content, re.S).group(1))
    return json.dumps(
        {
            "language": lang,
            "headline": f"[{lang}] {draft['headline']}",
            "sentences": [
                {"text": f"[{lang}] {s['text']}", "citations": s["citations"]}
                for s in draft["sentences"]
            ],
        }
    )


def critique(verdict="PASS", issues=()):
    return json.dumps(
        {
            "verdict": verdict,
            "issues": [{"severity": "MEDIUM", "description": d} for d in issues],
            "summary": "Reviewed." if verdict == "PASS" else "Needs work.",
        }
    )


def context_output(cite="E1"):
    return json.dumps(
        {
            "context_points": [
                {"text": "The official bulletin reports the 2023 rate.", "citations": [cite]}
            ],
            "missing_context": ["District-level figures"],
        }
    )
