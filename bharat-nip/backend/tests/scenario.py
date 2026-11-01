"""A scripted, fully fictional fact-checking scenario for pipeline tests.

Everything here (Riverland, its statistics office, the minister, the figures) is invented
for testing. Nothing describes a real place, person or statistic.

The mock LLM and mock search provider are scripted explicitly; nothing is auto-generated.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain.enums import (
    AuthorityLevel,
    EntityType,
    RegistryVerificationStatus,
    SourceCategory,
    SourceType,
    UserRole,
)
from app.ingest.extract import TesseractOCR
from app.ingest.fetcher import SafeFetcher
from app.models import Entity, RegistrySource, User
from app.pipeline.context import PipelineContext
from app.providers.llm.base import LLMRequest
from app.providers.llm.mock import MockLLMProvider
from app.providers.search.base import SearchHit
from app.providers.search.mock import MockSearchProvider
from app.services.users import create_user

SPEAKER_NAME = "Asha Verma"
CLAIM_SENTENCE = "Riverland's literacy rate rose to 81 percent in 2023."
SUBMISSION_TEXT = (
    f"At a rally on 2 March 2024, Minister {SPEAKER_NAME} said: "
    f'"{CLAIM_SENTENCE}" She added that the government was proud of its schools.'
)

STATS_URL = "https://stats.riverland.example/bulletins/literacy-2023"
STATS_TEXT = (
    "Riverland Statistics Office. Annual Education Bulletin 2023.\n\n"
    "The Riverland Statistics Office reports that the state literacy rate was 81.2 percent "
    "in 2023, up from 78.4 percent in 2021. The estimate comes from the 2023 household "
    "education survey covering 42,000 households across all districts.\n\n"
    "Methodology: literacy is defined as the ability to read and write a short statement "
    "in any language, for persons aged seven and above. The margin of error is 0.6 points."
)
STATS_QUOTE = "the state literacy rate was 81.2 percent in 2023, up from 78.4 percent in 2021"

NEWS_URL = "https://news.example.org/2024/01/riverland-literacy"
NEWS_TEXT = (
    "Riverland literacy edges up, survey finds\n\n"
    "An independent survey by the Riverland Education Trust put the state's literacy rate "
    "at 80.9 percent in 2023. Researchers said the rise was concentrated in rural districts, "
    "while urban literacy was broadly flat. The Trust's figures broadly match official data."
)
NEWS_QUOTE = "put the state's literacy rate at 80.9 percent in 2023"

PASSAGE_RE = re.compile(r"<<<PASSAGE id=(C\d+)>>>(.*?)<<<END PASSAGE>>>", re.S)


def passage_label(request: LLMRequest, needle: str) -> str:
    """Find which passage label (C1, C2, ...) contains ``needle`` in the rendered prompt."""
    for label, body in PASSAGE_RE.findall(request.messages[-1].content):
        if needle in body:
            return label
    raise AssertionError(f"no passage contains {needle!r}")


def extraction_response(
    *,
    text: str = CLAIM_SENTENCE,
    claim_type: str = "FACTUAL",
    speaker: str = SPEAKER_NAME,
) -> str:
    return json.dumps(
        {
            "claims": [
                {
                    "text": text,
                    "normalized_text": f"{speaker} said that {text}",
                    "subject": "Riverland's literacy rate",
                    "predicate": "rose to",
                    "object": "81 percent in 2023",
                    "claim_type": claim_type,
                    "checkworthy": claim_type == "FACTUAL",
                    "time_reference": "2023",
                    "claim_date": None,
                    "location": "Riverland",
                    "entities": [
                        {"name": speaker, "type": "PERSON", "role": "SPEAKER"},
                        {"name": "Riverland", "type": "PLACE", "role": "SUBJECT"},
                    ],
                }
            ]
        }
    )


def evidence_response(request: LLMRequest) -> str:
    return json.dumps(
        {
            "items": [
                {
                    "chunk": passage_label(request, STATS_QUOTE),
                    "quote": STATS_QUOTE,
                    "stance": "SUPPORTS",
                    "directness": "DIRECT",
                    "relevance": 0.95,
                    "rationale": "Official bulletin gives 81.2 percent for 2023.",
                },
                {
                    "chunk": passage_label(request, NEWS_QUOTE),
                    "quote": NEWS_QUOTE,
                    "stance": "SUPPORTS",
                    "directness": "DIRECT",
                    "relevance": 0.85,
                    "rationale": "Independent survey gives 80.9 percent for 2023.",
                },
            ]
        }
    )


def assessment_response(
    classification: str = "TRUE", confidence: float = 0.9, cited=("E1", "E2")
) -> str:
    return json.dumps(
        {
            "classification": classification,
            "confidence": confidence,
            "summary": "Official and independent figures put 2023 literacy at about 81 percent.",
            "reasoning": "E1 (official bulletin) reports 81.2 percent for 2023, up from 78.4 "
            "percent in 2021, so the rate rose. E2 (independent survey) reports 80.9 percent.",
            "cited_evidence": list(cited),
            "missing_information": ["District-level breakdown"],
            "recommended_action": "CONFIRM_IN_REVIEW",
        }
    )


CHECKS = [
    "source_quality",
    "outdated_evidence",
    "cherry_picking",
    "missing_context",
    "incorrect_interpretation",
    "contradictory_evidence",
    "unsupported_conclusions",
    "attribution_leakage",
]


def critic_response(outcome: str = "PASS", failing: tuple[str, ...] = ()) -> str:
    return json.dumps(
        {
            "outcome": outcome,
            "checks": [
                {
                    "check": c,
                    "passed": c not in failing,
                    "detail": "Issue found." if c in failing else "No issue found.",
                    "evidence": [],
                }
                for c in CHECKS
            ],
            "counter_argument": "The 81 percent figure is rounded; the official estimate is "
            "81.2 percent with a 0.6 point margin of error.",
            "suggested_classification": None,
            "summary": "Revise: mention the margin of error."
            if outcome == "REVISE"
            else "Assessment holds up.",
        }
    )


def stats_hit() -> SearchHit:
    return SearchHit(
        title="Annual Education Bulletin 2023",
        url=STATS_URL,
        publisher="Riverland Statistics Office",
        published_at=datetime(2024, 1, 15, tzinfo=UTC),
        content=STATS_TEXT,
        source_type=SourceType.STATISTICAL_DATA,
    )


def news_hit() -> SearchHit:
    return SearchHit(
        title="Riverland literacy edges up, survey finds",
        url=NEWS_URL,
        publisher="Example News",
        published_at=datetime(2024, 1, 20, tzinfo=UTC),
        content=NEWS_TEXT,
        source_type=SourceType.NEWS_REPORT,
    )


@dataclass
class World:
    submitter: User
    reviewer: User
    admin: User
    speaker: Entity
    llm: MockLLMProvider = field(default_factory=MockLLMProvider)
    search: MockSearchProvider = field(default_factory=MockSearchProvider)


PASSWORD = "correct-horse-battery"


def make_world(session: Session) -> World:
    admin = create_user(
        session,
        email="admin@test.example",
        display_name="Admin",
        role=UserRole.ADMIN,
        password=PASSWORD,
        created_by=None,
    )
    submitter = create_user(
        session,
        email="submitter@test.example",
        display_name="Sam Submitter",
        role=UserRole.ANALYST,
        password=PASSWORD,
        created_by=admin,
    )
    reviewer = create_user(
        session,
        email="reviewer@test.example",
        display_name="Rae Reviewer",
        role=UserRole.REVIEWER,
        password=PASSWORD,
        created_by=admin,
    )
    speaker = Entity(name=SPEAKER_NAME, entity_type=EntityType.PERSON)
    session.add(speaker)
    now = datetime.now(UTC)
    session.add(
        RegistrySource(
            name="Riverland Statistics Office",
            domain="stats.riverland.example",
            category=SourceCategory.STATISTICAL_AGENCY,
            jurisdiction="RL",
            authority_level=AuthorityLevel.PRIMARY_AUTHORITY,
            authority_scope=["literacy", "education", "census", "population"],
            authority_rationale="Statutory producer of official education statistics.",
            default_source_type=SourceType.STATISTICAL_DATA,
            is_primary_source=True,
            verification_status=RegistryVerificationStatus.VERIFIED,
            verification_method="Checked statutory mandate and published methodology.",
            verified_by_id=admin.id,
            verified_at=now,
            review_due_at=now + timedelta(days=365),
            created_by_id=admin.id,
        )
    )
    session.flush()
    return World(submitter=submitter, reviewer=reviewer, admin=admin, speaker=speaker)


def script_happy_path(world: World, *, revise_first: bool = True) -> None:
    world.llm.script("claim_extractor", extraction_response())
    world.search.script([stats_hit(), news_hit()], when_contains="literacy")
    world.llm.script("evidence_analyst", evidence_response)
    world.llm.script("assessor", assessment_response("TRUE", 0.95))
    if revise_first:
        world.llm.script("fact_check_critic", critic_response("REVISE", ("missing_context",)))
        world.llm.script("assessor", assessment_response("MOSTLY_TRUE", 0.85))
    world.llm.script("fact_check_critic", critic_response("PASS"))


def make_context(session: Session, settings: Settings, world: World) -> PipelineContext:
    return PipelineContext(
        session=session,
        settings=settings,
        llm=world.llm,
        critic_llm=world.llm,
        search_providers=[world.search],
        fetcher=SafeFetcher(settings),
        ocr=_NoOCR(),
    )


class _NoOCR(TesseractOCR):
    """Deterministic: tests never depend on whether tesseract is installed."""

    def __init__(self) -> None:
        super().__init__(binary=None)
        self.binary = None
