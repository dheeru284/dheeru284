"""API request/response schemas (API_DESIGN.md)."""

from __future__ import annotations

import base64
import uuid
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    AIRunStatus,
    AssessmentStatus,
    AuthorityLevel,
    ClaimStatus,
    ClaimType,
    Classification,
    EntityType,
    ExtractionMethod,
    FetchStatus,
    PipelineJobStatus,
    PipelineStage,
    ProducedBy,
    RecommendedAction,
    RegistryVerificationStatus,
    ReviewDecisionType,
    ReviewReason,
    ReviewStatus,
    ReviewTaskStatus,
    SearchStatus,
    SourceCategory,
    SourceType,
    SubmissionStatus,
    SubmissionType,
    UserRole,
)

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
Email = Annotated[str, Field(pattern=EMAIL_PATTERN, max_length=320)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(f"o:{offset}".encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        return max(0, int(raw.removeprefix("o:")))
    except (ValueError, UnicodeDecodeError):
        return 0


# --- auth / users ------------------------------------------------------------------------


class TokenRequest(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(ORM):
    id: uuid.UUID
    email: str
    display_name: str
    role: UserRole
    is_active: bool


class UserCreate(BaseModel):
    email: Email
    display_name: str = Field(min_length=1, max_length=200)
    role: UserRole
    password: str = Field(min_length=10, max_length=200)


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


# --- entities ----------------------------------------------------------------------------


class EntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    entity_type: EntityType
    description: str | None = Field(default=None, max_length=5000)


class EntityOut(ORM):
    id: uuid.UUID
    name: str
    entity_type: EntityType
    description: str | None


# --- submissions -------------------------------------------------------------------------


class SubmissionOut(ORM):
    id: uuid.UUID
    submitted_by_id: uuid.UUID
    submission_type: SubmissionType
    status: SubmissionStatus
    raw_text: str | None
    source_url: str | None
    title: str | None
    publisher_name: str | None
    published_at: datetime | None
    metadata: dict[str, Any] = Field(validation_alias="metadata_")
    file_id: uuid.UUID | None
    language: str
    context_note: str | None
    speaker_entity_id: uuid.UUID | None
    statement_date: date | None
    extraction_method: ExtractionMethod | None
    extraction_notes: str | None
    extracted_chars: int = 0
    created_at: datetime


class SubmissionCreated(BaseModel):
    submission: SubmissionOut
    created: bool


class TranscriptionIn(BaseModel):
    text: str = Field(min_length=20, max_length=20_000)


# --- claims ------------------------------------------------------------------------------


class ClaimOut(ORM):
    id: uuid.UUID
    submission_id: uuid.UUID
    text: str
    normalized_text: str
    subject: str
    predicate: str
    object: str = Field(validation_alias="object_")
    time_reference: str | None
    claim_date: date | None
    location: str | None
    entities: list[dict[str, Any]]
    original_source: dict[str, Any]
    claim_type: ClaimType
    checkworthy: bool
    language: str
    speaker_entity_id: uuid.UUID | None
    statement_date: date | None
    status: ClaimStatus
    review_status: ReviewStatus = ReviewStatus.NOT_READY
    extraction_ai_run_id: uuid.UUID | None
    extracted_at: datetime
    latest_classification: Classification | None = None
    latest_confidence: float | None = None


class PipelineJobOut(ORM):
    id: uuid.UUID
    stage: PipelineStage
    status: PipelineJobStatus
    attempt: int
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None


class SubmissionDetail(BaseModel):
    submission: SubmissionOut
    claims: list[ClaimOut]
    pipeline_jobs: list[PipelineJobOut]


class ClaimDetail(BaseModel):
    claim: ClaimOut
    pipeline_jobs: list[PipelineJobOut]
    open_review_task_id: uuid.UUID | None


class EvidenceOut(BaseModel):
    id: uuid.UUID
    quote: str
    quote_char_start: int
    quote_char_end: int
    stance: str
    stance_rationale: str
    directness: str
    relevance: float
    lexical_relevance: float
    agent_relevance: float | None
    extracted_by_ai_run_id: uuid.UUID | None
    rank_score: float | None
    rank_components: dict[str, Any] | None
    source: dict[str, Any]


class AssessmentOut(ORM):
    id: uuid.UUID
    revision: int
    parent_assessment_id: uuid.UUID | None
    classification: Classification
    confidence: float
    confidence_raw: float | None
    summary: str
    reasoning: str
    missing_information: list[str]
    recommended_action: RecommendedAction
    guardrails: list[dict[str, Any]]
    produced_by: ProducedBy
    ai_run_id: uuid.UUID | None
    status: AssessmentStatus
    created_at: datetime
    cited_evidence_ids: list[uuid.UUID] = []
    critiques: list[dict[str, Any]] = []


class SearchResultOut(ORM):
    rank: int
    url: str | None
    title: str
    snippet: str | None
    source_id: uuid.UUID | None
    fetch_status: FetchStatus
    fetch_error: str | None


class SearchQueryOut(ORM):
    id: uuid.UUID
    provider: str
    query_text: str
    status: SearchStatus
    result_count: int
    error: str | None
    executed_at: datetime
    results: list[SearchResultOut] = []


# --- registry / sources ------------------------------------------------------------------


class RegistryIn(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    domain: str | None = Field(default=None, max_length=255)
    category: SourceCategory
    jurisdiction: str = Field(min_length=2, max_length=20)
    authority_level: AuthorityLevel = AuthorityLevel.UNASSESSED
    authority_scope: list[str] = Field(default_factory=list, max_length=30)
    authority_rationale: str | None = Field(default=None, max_length=5000)
    default_source_type: SourceType = SourceType.OTHER
    is_primary_source: bool = False


class RegistryUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=300)
    domain: str | None = Field(default=None, max_length=255)
    category: SourceCategory | None = None
    jurisdiction: str | None = Field(default=None, max_length=20)
    authority_level: AuthorityLevel | None = None
    authority_scope: list[str] | None = None
    authority_rationale: str | None = Field(default=None, max_length=5000)
    default_source_type: SourceType | None = None
    is_primary_source: bool | None = None


class VerificationIn(BaseModel):
    status: RegistryVerificationStatus
    method: str = Field(min_length=3, max_length=2000)
    notes: str | None = Field(default=None, max_length=5000)
    review_period_days: int | None = Field(default=None, ge=1, le=1095)


class RegistryOut(ORM):
    id: uuid.UUID
    name: str
    domain: str | None
    category: SourceCategory
    jurisdiction: str
    authority_level: AuthorityLevel
    authority_scope: list[str]
    authority_rationale: str | None
    default_source_type: SourceType
    is_primary_source: bool
    verification_status: RegistryVerificationStatus
    verification_method: str | None
    verification_notes: str | None
    verified_by_id: uuid.UUID | None
    verified_at: datetime | None
    review_due_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SourceIn(BaseModel):
    title: str = Field(min_length=1, max_length=1000)
    url: str | None = Field(default=None, max_length=2048)
    publisher_name: str | None = Field(default=None, max_length=300)
    published_at: datetime | None = None
    source_type: SourceType
    language: str = Field(default="en", max_length=10)
    content_text: str = Field(min_length=20, max_length=2_000_000)


class SourceOut(ORM):
    id: uuid.UUID
    registry_source_id: uuid.UUID | None
    source_type: SourceType
    is_primary: bool
    title: str
    url: str | None
    publisher_name: str | None
    published_at: datetime | None
    retrieved_at: datetime
    retrieval_provider: str
    language: str
    content_sha256: str
    fetch_metadata: dict[str, Any]
    created_at: datetime


class SourceDetail(SourceOut):
    content_text: str


class SourceCreated(BaseModel):
    source: SourceOut
    created: bool


# --- review ------------------------------------------------------------------------------


class ReviewTaskOut(ORM):
    id: uuid.UUID
    claim_id: uuid.UUID
    assessment_id: uuid.UUID | None
    reason: ReviewReason
    reason_detail: str | None
    priority: int
    status: ReviewTaskStatus
    created_at: datetime
    claim_text: str | None = None
    proposed_classification: Classification | None = None
    proposed_confidence: float | None = None
    submitted_by_me: bool = False


class DecisionIn(BaseModel):
    decision: ReviewDecisionType
    final_classification: Classification | None = None
    notes: str | None = Field(default=None, max_length=5000)


class DecisionOut(ORM):
    id: uuid.UUID
    review_task_id: uuid.UUID
    reviewer_id: uuid.UUID
    decision: ReviewDecisionType
    final_classification: Classification | None
    notes: str | None
    created_at: datetime


# --- audit / ai runs ---------------------------------------------------------------------


class AuditEventOut(ORM):
    seq: int
    id: uuid.UUID
    occurred_at: datetime
    actor_type: str
    actor_id: str
    action: str
    entity_type: str
    entity_id: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str


class ChainVerificationOut(BaseModel):
    ok: bool
    checked: int
    first_broken_seq: int | None


class AIRunOut(ORM):
    id: uuid.UUID
    agent_name: str
    agent_version: str
    provider: str
    model: str
    prompt_id: str
    prompt_version: str
    prompt_sha256: str
    input_sha256: str
    input_messages: list[dict[str, Any]]
    parameters: dict[str, Any]
    output_text: str | None
    output_parsed: dict[str, Any] | None
    status: AIRunStatus
    error: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
    attempt: int
    pipeline_job_id: uuid.UUID | None
    created_at: datetime
