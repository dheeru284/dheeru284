"""Agent output schemas and specs. Each agent is a narrow function with an LLM inside:
typed input (rendered prompt), typed output, no tools, no side effects."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.runner import AgentSpec
from app.domain.enums import (
    ClaimType,
    Classification,
    CriticCheck,
    CriticOutcome,
    Directness,
    EntityRole,
    EntityType,
    RecommendedAction,
    Stance,
)

# --- claim extraction --------------------------------------------------------------------


class ExtractedEntity(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    type: EntityType
    role: EntityRole


class ExtractedClaim(BaseModel):
    text: str = Field(min_length=5, max_length=2000, description="The claim as stated.")
    normalized_text: str = Field(
        min_length=5,
        max_length=2000,
        description="Self-contained claim with the speaker replaced by [SPEAKER].",
    )
    subject: str = Field(min_length=1, max_length=500)
    predicate: str = Field(min_length=1, max_length=500)
    object: str = Field(min_length=1, max_length=1000)
    claim_type: ClaimType
    checkworthy: bool
    time_reference: str | None = Field(default=None, max_length=200)
    claim_date: str | None = Field(
        default=None, description="ISO date YYYY-MM-DD only if the exact day is stated."
    )
    location: str | None = Field(default=None, max_length=300)
    entities: list[ExtractedEntity] = Field(default_factory=list, max_length=20)


class ClaimExtractionOutput(BaseModel):
    claims: list[ExtractedClaim] = Field(max_length=20)


CLAIM_EXTRACTOR = AgentSpec(
    name="claim_extractor",
    version="1.0",
    prompt_id="claim_extractor",
    prompt_version="v1",
    output_model=ClaimExtractionOutput,
    max_tokens=4096,
)

# --- evidence analysis -------------------------------------------------------------------


class EvidenceProposal(BaseModel):
    chunk: str = Field(pattern=r"^C\d+$", description="Label of the passage, e.g. C3.")
    quote: str = Field(min_length=10, max_length=1500, description="Verbatim from the passage.")
    stance: Stance
    directness: Directness
    relevance: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=5, max_length=1000)


class EvidenceAnalysisOutput(BaseModel):
    items: list[EvidenceProposal] = Field(max_length=30)


EVIDENCE_ANALYST = AgentSpec(
    name="evidence_analyst",
    version="1.0",
    prompt_id="evidence_analyst",
    prompt_version="v1",
    output_model=EvidenceAnalysisOutput,
    max_tokens=4096,
)

# --- assessment --------------------------------------------------------------------------


class AssessmentProposal(BaseModel):
    classification: Classification
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=10, max_length=1000)
    reasoning: str = Field(min_length=10, max_length=5000)
    cited_evidence: list[str] = Field(default_factory=list, max_length=30)
    missing_information: list[str] = Field(default_factory=list, max_length=20)
    recommended_action: RecommendedAction


ASSESSOR = AgentSpec(
    name="assessor",
    version="1.0",
    prompt_id="assessor",
    prompt_version="v1",
    output_model=AssessmentProposal,
    max_tokens=3072,
)

# --- critic ------------------------------------------------------------------------------


class CriticCheckResult(BaseModel):
    check: CriticCheck
    passed: bool
    detail: str = Field(min_length=3, max_length=2000)
    evidence: list[str] = Field(default_factory=list, max_length=30)


class CritiqueProposal(BaseModel):
    outcome: CriticOutcome
    checks: list[CriticCheckResult]
    counter_argument: str = Field(min_length=10, max_length=3000)
    suggested_classification: Classification | None = None
    summary: str = Field(min_length=10, max_length=2000)


FACT_CHECK_CRITIC = AgentSpec(
    name="fact_check_critic",
    version="1.0",
    prompt_id="fact_check_critic",
    prompt_version="v1",
    output_model=CritiqueProposal,
    max_tokens=3072,
)

assert FACT_CHECK_CRITIC.name != ASSESSOR.name  # an agent never reviews its own work
