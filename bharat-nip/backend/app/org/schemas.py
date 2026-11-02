"""Typed input and output schemas for every organization agent (exposed as JSON Schema)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.enums import Recommendation

# --- workflow inputs ---------------------------------------------------------------------


class SubmissionTaskInput(BaseModel):
    submission_id: uuid.UUID


class ClaimTaskInput(BaseModel):
    claim_id: uuid.UUID


class NarrativeResponseInput(BaseModel):
    narrative_id: uuid.UUID
    languages: list[str] = Field(default_factory=list, max_length=6)


class AnalyticsTaskInput(BaseModel):
    window_days: int = Field(default=30, ge=1, le=365)


# --- shared ------------------------------------------------------------------------------


class CitedSentence(BaseModel):
    text: str = Field(min_length=3, max_length=1000)
    citations: list[str] = Field(default_factory=list, max_length=10)


class ReviewIssue(BaseModel):
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    description: str = Field(min_length=3, max_length=1000)


# --- chief -------------------------------------------------------------------------------


class ChiefInput(BaseModel):
    workflow: str
    title: str
    input: dict[str, Any]


class DelegationPlan(BaseModel):
    steps: list[dict[str, Any]]


# --- claim extraction / research / verification / fact check ------------------------------


class ExtractionOutput(BaseModel):
    submission_status: str
    extraction_method: str | None
    claims: list[dict[str, Any]]


class ResearchInput(BaseModel):
    claim_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


class ResearchOutput(BaseModel):
    claims: list[dict[str, Any]]


class SourceVerificationOutput(BaseModel):
    sources: list[dict[str, Any]]
    summary_flags: list[str]


class FactCheckInput(BaseModel):
    claim_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


class FactCheckOutput(BaseModel):
    claims: list[dict[str, Any]]
    pending_human_review: int


class ContextOutput(BaseModel):
    context_points: list[CitedSentence] = Field(max_length=10)
    missing_context: list[str] = Field(default_factory=list, max_length=10)


class MediaForensicsOutput(BaseModel):
    file: dict[str, Any] | None
    reuse: list[dict[str, Any]]
    findings: list[str]
    limitations: list[str]


# --- narrative / analytics / communications ----------------------------------------------


class NarrativeBrief(BaseModel):
    narrative_id: str
    title: str
    status: str
    recommendation: Recommendation
    rule: str
    rationale: str
    evidence_status: str
    momentum: float
    public_interest: float
    harm_severity: str
    coverage: float
    facts: list[dict[str, Any]]


class AnalyticsOutput(BaseModel):
    window_days: int
    claims_by_classification: dict[str, int]
    review_backlog: int
    narratives_by_recommendation: dict[str, int]
    narrative_trend: list[dict[str, Any]]
    agent_executions: dict[str, int]


OwnChannel = Literal[
    "OFFICIAL_WEBSITE", "OFFICIAL_SOCIAL_ACCOUNT", "PRESS_BRIEFING", "FACT_CHECK_PAGE"
]
ContentFormat = Literal["EXPLAINER", "CORRECTION", "CONTEXT_NOTE", "NONE"]


class StrategyOutput(BaseModel):
    posture: Recommendation
    objectives: list[str] = Field(max_length=5)
    key_messages: list[CitedSentence] = Field(max_length=6)
    channels: list[OwnChannel] = Field(default_factory=list, max_length=4)
    format: ContentFormat
    do_not: list[str] = Field(default_factory=list, max_length=8)


class ContentDraft(BaseModel):
    format: ContentFormat
    headline: str = Field(min_length=3, max_length=200)
    sentences: list[CitedSentence] = Field(min_length=1, max_length=12)
    ai_assisted_label: str


class Translation(BaseModel):
    language: str
    headline: str = Field(min_length=1, max_length=400)
    sentences: list[CitedSentence] = Field(min_length=1, max_length=12)


class LocalizationOutput(BaseModel):
    translations: list[Translation]
    note: str


class OrgCritique(BaseModel):
    verdict: Literal["PASS", "REVISE", "ESCALATE"]
    issues: list[ReviewIssue] = Field(default_factory=list, max_length=12)
    summary: str = Field(min_length=3, max_length=1500)


class ComplianceOutput(BaseModel):
    passed: bool
    violations: list[dict[str, str]]
    warnings: list[dict[str, str]]
