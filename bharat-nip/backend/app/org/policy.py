"""Permissions, escalation conditions and global bounds for the agent organization."""

from __future__ import annotations

from enum import StrEnum

ORG_VERSION = "org-v1"

MAX_EXECUTIONS_PER_TASK = 40
MAX_HUMAN_REVISIONS = 2
MAX_STEP_RETRIES = 1
CHARS_PER_TOKEN = 4  # conservative estimate used to enforce input token limits

AI_ASSISTED_LABEL = "AI-assisted draft. Reviewed by people before any use."
MACHINE_TRANSLATION_NOTE = "Machine translation: needs review by a fluent human reviewer."

SUPPORTED_LANGUAGES = {
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
    "or": "Odia",
    "as": "Assamese",
}


class Permission(StrEnum):
    """What an agent may do. There is deliberately no permission to publish, send, post,
    schedule or contact anyone, and none to approve externally facing work."""

    DELEGATE = "DELEGATE"
    APPROVE_INTERNAL = "APPROVE_INTERNAL"
    READ_SUBMISSIONS = "READ_SUBMISSIONS"
    READ_CLAIMS = "READ_CLAIMS"
    READ_EVIDENCE = "READ_EVIDENCE"
    READ_REGISTRY = "READ_REGISTRY"
    READ_MEDIA = "READ_MEDIA"
    READ_FACT_CHECKS = "READ_FACT_CHECKS"
    READ_NARRATIVES = "READ_NARRATIVES"
    READ_ANALYTICS = "READ_ANALYTICS"
    RUN_PIPELINE = "RUN_PIPELINE"
    RUN_ANALYSIS = "RUN_ANALYSIS"
    DRAFT_CONTENT = "DRAFT_CONTENT"
    TRANSLATE_CONTENT = "TRANSLATE_CONTENT"
    REVIEW_WORK = "REVIEW_WORK"
    CHECK_COMPLIANCE = "CHECK_COMPLIANCE"


class EscalationCondition(StrEnum):
    ITERATION_LIMIT = "ITERATION_LIMIT"
    TOKEN_LIMIT = "TOKEN_LIMIT"
    REVIEW_ESCALATED = "REVIEW_ESCALATED"
    COMPLIANCE_VIOLATION = "COMPLIANCE_VIOLATION"
    NO_APPROVED_EVIDENCE = "NO_APPROVED_EVIDENCE"
    TOOL_FAILURE = "TOOL_FAILURE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TASK_BUDGET = "TASK_BUDGET"
    INVALID_OUTPUT = "INVALID_OUTPUT"


class EscalationTarget(StrEnum):
    MANAGER = "MANAGER"  # recorded against the manager, then passed to a human
    HUMAN = "HUMAN"


class ModelRole(StrEnum):
    PRIMARY = "primary"  # BNIP_LLM_PROVIDER / BNIP_OLLAMA_MODEL
    CRITIC = "critic"  # BNIP_OLLAMA_CRITIC_MODEL (independent reviewer)
    RULES = "rules"  # deterministic code, no model


class OrgError(Exception):
    condition = EscalationCondition.TOOL_FAILURE

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class PermissionDenied(OrgError):
    condition = EscalationCondition.PERMISSION_DENIED


class TokenLimitExceeded(OrgError):
    condition = EscalationCondition.TOKEN_LIMIT


class NoApprovedEvidence(OrgError):
    condition = EscalationCondition.NO_APPROVED_EVIDENCE


class InvalidAgentOutputError(OrgError):
    condition = EscalationCondition.INVALID_OUTPUT
