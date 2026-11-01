"""Closed vocabularies. The single source of truth for enum values (DB CHECK constraints,
API schemas and prompts are all derived from these)."""

from __future__ import annotations

from enum import StrEnum


class Verdict(StrEnum):
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


# Verdicts that make an affirmative factual determination and therefore need >=1 citation.
VERDICTS_REQUIRING_CITATION = frozenset(
    {
        Verdict.TRUE,
        Verdict.MOSTLY_TRUE,
        Verdict.MISLEADING,
        Verdict.OUT_OF_CONTEXT,
        Verdict.FALSE,
    }
)


class Confidence(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ClaimType(StrEnum):
    FACTUAL = "FACTUAL"
    OPINION = "OPINION"
    PREDICTION = "PREDICTION"
    SATIRE = "SATIRE"
    UNCLEAR = "UNCLEAR"


# Non-checkable claim types map directly to a verdict by rule.
NON_CHECKABLE_VERDICT = {
    ClaimType.OPINION: Verdict.OPINION,
    ClaimType.PREDICTION: Verdict.PREDICTION,
    ClaimType.SATIRE: Verdict.SATIRE,
}


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    REVIEWER = "REVIEWER"
    ANALYST = "ANALYST"
    SUBMITTER = "SUBMITTER"


class EntityType(StrEnum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    POLITICAL_PARTY = "POLITICAL_PARTY"
    GOVERNMENT_BODY = "GOVERNMENT_BODY"
    MEDIA_OUTLET = "MEDIA_OUTLET"
    OTHER = "OTHER"


class SubmissionStatus(StrEnum):
    RECEIVED = "RECEIVED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"


class ClaimStatus(StrEnum):
    EXTRACTED = "EXTRACTED"
    RETRIEVING = "RETRIEVING"
    EVIDENCE_READY = "EVIDENCE_READY"
    ASSESSING = "ASSESSING"
    CRITIQUING = "CRITIQUING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ReliabilityTier(StrEnum):
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"
    TIER_4 = "TIER_4"
    UNRATED = "UNRATED"


class SourceType(StrEnum):
    OFFICIAL_RECORD = "OFFICIAL_RECORD"
    STATISTICAL_DATA = "STATISTICAL_DATA"
    LEGAL_DOCUMENT = "LEGAL_DOCUMENT"
    ACADEMIC = "ACADEMIC"
    NEWS_REPORT = "NEWS_REPORT"
    FACT_CHECK = "FACT_CHECK"
    PRESS_RELEASE = "PRESS_RELEASE"
    OTHER = "OTHER"


class RetrievalMethod(StrEnum):
    VECTOR = "VECTOR"
    KEYWORD = "KEYWORD"
    HYBRID = "HYBRID"


class Stance(StrEnum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    MIXED = "MIXED"
    CONTEXT = "CONTEXT"
    NOT_RELEVANT = "NOT_RELEVANT"


class ProducedBy(StrEnum):
    AGENT = "AGENT"
    RULE = "RULE"


class AssessmentStatus(StrEnum):
    DRAFT = "DRAFT"
    CRITIQUED = "CRITIQUED"
    SUPERSEDED = "SUPERSEDED"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    AMENDED = "AMENDED"
    REJECTED = "REJECTED"


class CriticOutcome(StrEnum):
    PASS = "PASS"
    REVISE = "REVISE"
    ESCALATE = "ESCALATE"


class ReviewReason(StrEnum):
    ROUTINE = "ROUTINE"
    CRITIC_ESCALATION = "CRITIC_ESCALATION"
    LOOP_LIMIT = "LOOP_LIMIT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    STAGE_FAILURE = "STAGE_FAILURE"


class ReviewTaskStatus(StrEnum):
    OPEN = "OPEN"
    CLAIMED = "CLAIMED"
    DECIDED = "DECIDED"
    CANCELLED = "CANCELLED"


class ReviewDecisionType(StrEnum):
    APPROVE = "APPROVE"
    AMEND = "AMEND"
    REJECT = "REJECT"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"


class AIRunStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    INVALID_OUTPUT = "INVALID_OUTPUT"


class PipelineStage(StrEnum):
    EXTRACTION = "EXTRACTION"
    RETRIEVAL = "RETRIEVAL"
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
