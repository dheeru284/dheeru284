"""Closed vocabularies. The single source of truth for enum values (DB CHECK constraints,
API schemas and prompts are all derived from these). A test verifies that every
CHECK constraint in the database matches these values."""

from __future__ import annotations

from enum import StrEnum


class Classification(StrEnum):
    """Fact-check classification (PRODUCT_REQUIREMENTS.md §4)."""

    TRUE = "TRUE"
    MOSTLY_TRUE = "MOSTLY_TRUE"
    MISLEADING = "MISLEADING"
    OUT_OF_CONTEXT = "OUT_OF_CONTEXT"
    FALSE = "FALSE"
    UNVERIFIED = "UNVERIFIED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    OPINION = "OPINION"
    PREDICTION = "PREDICTION"
    SATIRE = "SATIRE"


# Backwards-compatible alias used in Phase 0 code and docs.
Verdict = Classification

# Classifications that make an affirmative factual determination and need >=1 citation.
CLASSIFICATIONS_REQUIRING_CITATION = frozenset(
    {
        Classification.TRUE,
        Classification.MOSTLY_TRUE,
        Classification.MISLEADING,
        Classification.OUT_OF_CONTEXT,
        Classification.FALSE,
    }
)
VERDICTS_REQUIRING_CITATION = CLASSIFICATIONS_REQUIRING_CITATION

# Classifications that are not an evidential determination about truth.
NON_DETERMINATIONS = frozenset(
    {
        Classification.UNVERIFIED,
        Classification.INSUFFICIENT_EVIDENCE,
        Classification.OPINION,
        Classification.PREDICTION,
        Classification.SATIRE,
    }
)


class RecommendedAction(StrEnum):
    CONFIRM_IN_REVIEW = "CONFIRM_IN_REVIEW"
    ADD_CONTEXT_NOTE = "ADD_CONTEXT_NOTE"
    SEEK_PRIMARY_SOURCE = "SEEK_PRIMARY_SOURCE"
    GATHER_MORE_EVIDENCE = "GATHER_MORE_EVIDENCE"
    CONSULT_SUBJECT_EXPERT = "CONSULT_SUBJECT_EXPERT"
    NOT_FACT_CHECKABLE = "NOT_FACT_CHECKABLE"


class ClaimType(StrEnum):
    FACTUAL = "FACTUAL"
    OPINION = "OPINION"
    PREDICTION = "PREDICTION"
    SATIRE = "SATIRE"
    UNCLEAR = "UNCLEAR"


# Non-checkable claim types map directly to a classification by rule.
NON_CHECKABLE_VERDICT = {
    ClaimType.OPINION: Classification.OPINION,
    ClaimType.PREDICTION: Classification.PREDICTION,
    ClaimType.SATIRE: Classification.SATIRE,
}


class EntityRole(StrEnum):
    SPEAKER = "SPEAKER"  # who made the claim; removed from the blinded text
    SUBJECT = "SUBJECT"  # what the claim is about; kept (removing it makes it uncheckable)
    MENTIONED = "MENTIONED"


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    REVIEWER = "REVIEWER"
    ANALYST = "ANALYST"
    SUBMITTER = "SUBMITTER"


ROLE_RANK = {UserRole.SUBMITTER: 0, UserRole.ANALYST: 1, UserRole.REVIEWER: 2, UserRole.ADMIN: 3}


class EntityType(StrEnum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    POLITICAL_PARTY = "POLITICAL_PARTY"
    GOVERNMENT_BODY = "GOVERNMENT_BODY"
    MEDIA_OUTLET = "MEDIA_OUTLET"
    PLACE = "PLACE"
    OTHER = "OTHER"


class SubmissionType(StrEnum):
    TEXT = "TEXT"
    URL = "URL"
    ARTICLE = "ARTICLE"
    IMAGE = "IMAGE"
    PDF = "PDF"
    VIDEO_METADATA = "VIDEO_METADATA"


class SubmissionStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    NEEDS_TRANSCRIPTION = (
        "NEEDS_TRANSCRIPTION"  # no machine-readable text (e.g. image, scanned PDF)
    )
    NO_CLAIMS = "NO_CLAIMS"
    FAILED = "FAILED"


class ExtractionMethod(StrEnum):
    USER_TEXT = "USER_TEXT"
    HTML_EXTRACTION = "HTML_EXTRACTION"
    PDF_TEXT = "PDF_TEXT"
    OCR = "OCR"
    USER_TRANSCRIPTION = "USER_TRANSCRIPTION"
    VIDEO_METADATA = "VIDEO_METADATA"


class ClaimStatus(StrEnum):
    EXTRACTED = "EXTRACTED"
    RESEARCHING = "RESEARCHING"
    ASSESSING = "ASSESSING"
    CRITIQUING = "CRITIQUING"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_MORE_RESEARCH = "NEEDS_MORE_RESEARCH"
    FAILED = "FAILED"


class ReviewStatus(StrEnum):
    """Human-review view of a claim (derived from ClaimStatus)."""

    NOT_READY = "NOT_READY"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_MORE_RESEARCH = "NEEDS_MORE_RESEARCH"


# --- Source registry ---------------------------------------------------------------------


class SourceCategory(StrEnum):
    GOVERNMENT = "GOVERNMENT"
    STATISTICAL_AGENCY = "STATISTICAL_AGENCY"
    REGULATOR = "REGULATOR"
    COURT = "COURT"
    LEGISLATURE = "LEGISLATURE"
    ELECTION_BODY = "ELECTION_BODY"
    INTERNATIONAL_ORGANIZATION = "INTERNATIONAL_ORGANIZATION"
    ACADEMIC = "ACADEMIC"
    NEWS_MEDIA = "NEWS_MEDIA"
    FACT_CHECKER = "FACT_CHECKER"
    NGO = "NGO"
    CORPORATE = "CORPORATE"
    POLITICAL_PARTY = "POLITICAL_PARTY"
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    OTHER = "OTHER"


class AuthorityLevel(StrEnum):
    """How authoritative a registered source is *within its declared scope and jurisdiction*.

    This is not a truth label. It is time-limited (review_due_at) and only counts while
    the registry entry is VERIFIED and in date.
    """

    PRIMARY_AUTHORITY = "PRIMARY_AUTHORITY"  # the body that produces the record/data
    ESTABLISHED = "ESTABLISHED"  # documented methodology and corrections practice
    GENERAL = "GENERAL"
    LIMITED = "LIMITED"  # documented, specific reasons for caution
    UNASSESSED = "UNASSESSED"


class RegistryVerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    DISPUTED = "DISPUTED"


class SourceType(StrEnum):
    OFFICIAL_RECORD = "OFFICIAL_RECORD"
    STATISTICAL_DATA = "STATISTICAL_DATA"
    LEGAL_DOCUMENT = "LEGAL_DOCUMENT"
    ACADEMIC = "ACADEMIC"
    NEWS_REPORT = "NEWS_REPORT"
    FACT_CHECK = "FACT_CHECK"
    PRESS_RELEASE = "PRESS_RELEASE"
    SOCIAL_MEDIA_POST = "SOCIAL_MEDIA_POST"
    OTHER = "OTHER"


PRIMARY_SOURCE_TYPES = frozenset(
    {SourceType.OFFICIAL_RECORD, SourceType.STATISTICAL_DATA, SourceType.LEGAL_DOCUMENT}
)


# --- Search and evidence -----------------------------------------------------------------


class SearchStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class FetchStatus(StrEnum):
    FETCHED = "FETCHED"
    PROVIDED = "PROVIDED"  # provider returned full content (local corpus, mock)
    REUSED = "REUSED"  # identical content already stored
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class Stance(StrEnum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    MIXED = "MIXED"
    CONTEXT = "CONTEXT"
    NOT_RELEVANT = "NOT_RELEVANT"


USABLE_STANCES = frozenset({Stance.SUPPORTS, Stance.REFUTES, Stance.MIXED, Stance.CONTEXT})


class Directness(StrEnum):
    DIRECT = "DIRECT"  # addresses the specific claim (same quantity, event, period)
    INDIRECT = "INDIRECT"  # related background


class ProducedBy(StrEnum):
    AGENT = "AGENT"
    RULE = "RULE"


class AssessmentStatus(StrEnum):
    DRAFT = "DRAFT"
    CRITIQUED = "CRITIQUED"
    SUPERSEDED = "SUPERSEDED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_MORE_RESEARCH = "NEEDS_MORE_RESEARCH"


class CriticOutcome(StrEnum):
    PASS = "PASS"
    REVISE = "REVISE"
    ESCALATE = "ESCALATE"


class CriticCheck(StrEnum):
    SOURCE_QUALITY = "source_quality"
    OUTDATED_EVIDENCE = "outdated_evidence"
    CHERRY_PICKING = "cherry_picking"
    MISSING_CONTEXT = "missing_context"
    INCORRECT_INTERPRETATION = "incorrect_interpretation"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"
    UNSUPPORTED_CONCLUSIONS = "unsupported_conclusions"
    ATTRIBUTION_LEAKAGE = "attribution_leakage"


class FindingSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ReviewReason(StrEnum):
    ROUTINE = "ROUTINE"
    CRITIC_ESCALATION = "CRITIC_ESCALATION"
    RULE_FLAG = "RULE_FLAG"
    LOOP_LIMIT = "LOOP_LIMIT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    STAGE_FAILURE = "STAGE_FAILURE"


class ReviewTaskStatus(StrEnum):
    OPEN = "OPEN"
    DECIDED = "DECIDED"
    CANCELLED = "CANCELLED"


class ReviewDecisionType(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    NEEDS_MORE_RESEARCH = "NEEDS_MORE_RESEARCH"


class AIRunStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    INVALID_OUTPUT = "INVALID_OUTPUT"


class PipelineStage(StrEnum):
    CONTENT = "CONTENT"
    EXTRACTION = "EXTRACTION"
    SEARCH = "SEARCH"
    EVIDENCE = "EVIDENCE"
    RANKING = "RANKING"
    ASSESSMENT = "ASSESSMENT"
    CRITIQUE = "CRITIQUE"
    REVIEW_ROUTING = "REVIEW_ROUTING"


class PipelineJobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


class ActorType(StrEnum):
    USER = "USER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


# --- Narrative intelligence (NARRATIVE_INTELLIGENCE.md) ----------------------------------


class NarrativeStatus(StrEnum):
    EMERGING = "EMERGING"
    MONITOR = "MONITOR"
    INVESTIGATE = "INVESTIGATE"
    RESPOND = "RESPOND"
    CORRECT = "CORRECT"
    RESOLVED = "RESOLVED"
    ARCHIVED = "ARCHIVED"


class Recommendation(StrEnum):
    RESPOND = "RESPOND"
    MONITOR = "MONITOR"
    INVESTIGATE = "INVESTIGATE"
    CORRECT = "CORRECT"
    IGNORE = "IGNORE"
    ESCALATE = "ESCALATE"


class EvidenceStatus(StrEnum):
    VERIFIED_FALSE = "VERIFIED_FALSE"
    VERIFIED_TRUE = "VERIFIED_TRUE"
    CONTESTED = "CONTESTED"
    UNRESOLVED = "UNRESOLVED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    NOT_CHECKABLE = "NOT_CHECKABLE"


class HarmCategory(StrEnum):
    NONE = "NONE"
    PUBLIC_HEALTH = "PUBLIC_HEALTH"
    PUBLIC_SAFETY = "PUBLIC_SAFETY"
    ELECTORAL_PROCESS = "ELECTORAL_PROCESS"
    COMMUNAL_HARMONY = "COMMUNAL_HARMONY"
    FINANCIAL_FRAUD = "FINANCIAL_FRAUD"
    OTHER = "OTHER"


class HarmSeverity(StrEnum):
    UNASSESSED = "UNASSESSED"
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class NarrativeOrigin(StrEnum):
    DETECTED = "DETECTED"
    MANUAL = "MANUAL"


class MembershipSource(StrEnum):
    ENGINE = "ENGINE"
    USER = "USER"


class RelationType(StrEnum):
    SIMILAR = "SIMILAR"
    SAME_TOPIC = "SAME_TOPIC"
    SHARES_ENTITY = "SHARES_ENTITY"
    SHARES_EVIDENCE = "SHARES_EVIDENCE"
    CONTRADICTS = "CONTRADICTS"


class ObservationMetric(StrEnum):
    """Aggregate public counts only. Never per person or per account."""

    MENTIONS = "MENTIONS"
    SHARES = "SHARES"
    VIEWS = "VIEWS"
    ARTICLES = "ARTICLES"
    SEARCH_INTEREST = "SEARCH_INTEREST"


class ResponseType(StrEnum):
    FACT_CHECK = "FACT_CHECK"
    CORRECTION = "CORRECTION"
    CLARIFICATION = "CLARIFICATION"
    CONTEXT_NOTE = "CONTEXT_NOTE"
    EXTERNAL_FACT_CHECK = "EXTERNAL_FACT_CHECK"


# --- Agent organization (AGENT_ORGANIZATION.md) ------------------------------------------


class WorkflowType(StrEnum):
    SUBMISSION_FACT_CHECK = "SUBMISSION_FACT_CHECK"
    CLAIM_INVESTIGATION = "CLAIM_INVESTIGATION"
    MEDIA_CHECK = "MEDIA_CHECK"
    NARRATIVE_RESPONSE = "NARRATIVE_RESPONSE"
    ANALYTICS_REPORT = "ANALYTICS_REPORT"


class OrgTaskStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    ESCALATED = "ESCALATED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    IN_REVIEW = "IN_REVIEW"
    DONE = "DONE"
    SKIPPED = "SKIPPED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


class ReviewerType(StrEnum):
    CRITIC = "CRITIC"
    MANAGER = "MANAGER"
    NONE = "NONE"


class ApprovalLevel(StrEnum):
    MANAGER = "MANAGER"  # internal work: approved by the Chief Intelligence Agent
    HUMAN = "HUMAN"  # anything meant for the public: approved by a person


class ExecutionKind(StrEnum):
    DELEGATION = "DELEGATION"
    EXECUTION = "EXECUTION"
    REVIEW = "REVIEW"
    REVISION = "REVISION"
    ESCALATION = "ESCALATION"
    APPROVAL = "APPROVAL"
    COMPLETION = "COMPLETION"


class ExecutionStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PASS = "PASS"
    REVISE = "REVISE"
    ESCALATE = "ESCALATE"
    SKIPPED = "SKIPPED"


class ApproverType(StrEnum):
    HUMAN = "HUMAN"
    AGENT = "AGENT"


class ApprovalDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
