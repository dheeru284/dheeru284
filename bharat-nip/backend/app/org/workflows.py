"""Explicit workflow templates (AGENT_ORGANIZATION.md §5). The only way work moves between
agents: each step's input is built from the task input and named upstream outputs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.domain.enums import ApprovalLevel, ReviewerType, WorkflowType
from app.org import schemas as S

Outputs = dict[str, Any]  # step_key -> output, plus "_task" -> task input


@dataclass(frozen=True)
class StepSpec:
    key: str
    agent: str
    reviewer: ReviewerType
    depends_on: tuple[str, ...]
    build_input: Callable[[Outputs], dict[str, Any]]
    # Returns a skip reason, or None to run the step.
    skip_if: Callable[[Outputs], str | None] = lambda _o: None
    # LLM steps that a human may ask to revise.
    revisable: bool = False


@dataclass(frozen=True)
class Workflow:
    type: WorkflowType
    input_schema: type[BaseModel]
    approval: ApprovalLevel
    title: Callable[[dict[str, Any]], str]
    steps: tuple[StepSpec, ...]


def _claim_ids(o: Outputs) -> list[str]:
    return [c["claim_id"] for c in o["extract"]["claims"]]


M, C, N = ReviewerType.MANAGER, ReviewerType.CRITIC, ReviewerType.NONE

WORKFLOWS: dict[WorkflowType, Workflow] = {
    w.type: w
    for w in [
        Workflow(
            WorkflowType.SUBMISSION_FACT_CHECK,
            S.SubmissionTaskInput,
            ApprovalLevel.MANAGER,
            lambda i: f"Fact-check submission {str(i['submission_id'])[:8]}",
            (
                StepSpec(
                    "extract",
                    "claim_extraction_agent",
                    M,
                    (),
                    lambda o: {"submission_id": o["_task"]["submission_id"]},
                ),
                StepSpec(
                    "research",
                    "research_agent",
                    M,
                    ("extract",),
                    lambda o: {"claim_ids": _claim_ids(o)},
                    skip_if=lambda o: None if _claim_ids(o) else "no claims extracted",
                ),
                StepSpec(
                    "fact_check",
                    "fact_check_agent",
                    M,
                    ("research",),
                    lambda o: {"claim_ids": _claim_ids(o)},
                    skip_if=lambda o: None if _claim_ids(o) else "no claims extracted",
                ),
            ),
        ),
        Workflow(
            WorkflowType.CLAIM_INVESTIGATION,
            S.ClaimTaskInput,
            ApprovalLevel.MANAGER,
            lambda i: f"Investigate claim {str(i['claim_id'])[:8]}",
            (
                StepSpec(
                    "research",
                    "research_agent",
                    M,
                    (),
                    lambda o: {"claim_ids": [o["_task"]["claim_id"]]},
                ),
                StepSpec(
                    "sources",
                    "source_verification_agent",
                    M,
                    ("research",),
                    lambda o: {"claim_id": o["_task"]["claim_id"]},
                ),
                StepSpec(
                    "context",
                    "context_agent",
                    C,
                    ("research",),
                    lambda o: {"claim_id": o["_task"]["claim_id"]},
                    revisable=True,
                ),
                StepSpec(
                    "fact_check",
                    "fact_check_agent",
                    M,
                    ("research",),
                    lambda o: {"claim_ids": [o["_task"]["claim_id"]]},
                ),
            ),
        ),
        Workflow(
            WorkflowType.MEDIA_CHECK,
            S.SubmissionTaskInput,
            ApprovalLevel.MANAGER,
            lambda i: f"Media check for submission {str(i['submission_id'])[:8]}",
            (
                StepSpec(
                    "media",
                    "media_forensics_agent",
                    M,
                    (),
                    lambda o: {"submission_id": o["_task"]["submission_id"]},
                ),
            ),
        ),
        Workflow(
            WorkflowType.NARRATIVE_RESPONSE,
            S.NarrativeResponseInput,
            ApprovalLevel.HUMAN,
            lambda i: f"Response package for narrative {str(i['narrative_id'])[:8]}",
            (
                StepSpec("narrative", "narrative_intelligence_agent", M, (), lambda o: o["_task"]),
                StepSpec(
                    "analytics", "analytics_agent", M, ("narrative",), lambda o: {"window_days": 30}
                ),
                StepSpec(
                    "strategy",
                    "response_strategist",
                    C,
                    ("narrative",),
                    lambda o: o["narrative"],
                    revisable=True,
                ),
                StepSpec(
                    "content",
                    "content_agent",
                    C,
                    ("strategy", "narrative"),
                    lambda o: o["strategy"],
                    skip_if=lambda o: (
                        "no public response recommended"
                        if o["strategy"]["format"] == "NONE"
                        else None
                    ),
                    revisable=True,
                ),
                StepSpec(
                    "localization",
                    "localization_agent",
                    C,
                    ("content",),
                    lambda o: o["content"],
                    skip_if=lambda o: (
                        "no content to translate"
                        if not o.get("content")
                        else ("no languages requested" if not o["_task"].get("languages") else None)
                    ),
                    revisable=True,
                ),
                StepSpec(
                    "compliance",
                    "compliance_agent",
                    N,
                    ("content", "localization"),
                    lambda o: o["content"],
                    skip_if=lambda o: "no content to check" if not o.get("content") else None,
                ),
            ),
        ),
        Workflow(
            WorkflowType.ANALYTICS_REPORT,
            S.AnalyticsTaskInput,
            ApprovalLevel.MANAGER,
            lambda i: f"Analytics report ({i.get('window_days', 30)} days)",
            (
                StepSpec(
                    "analytics",
                    "analytics_agent",
                    M,
                    (),
                    lambda o: {"window_days": o["_task"].get("window_days", 30)},
                ),
            ),
        ),
    ]
}
