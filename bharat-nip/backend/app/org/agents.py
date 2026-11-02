"""The fourteen organization agents (AGENT_ORGANIZATION.md §2-§3).

Definitions are code, not data: changing an agent's permissions, tools, limits or escalation
rules is a reviewed code change. The API exposes these definitions read-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel

from app.org import schemas as S
from app.org.policy import EscalationCondition as E
from app.org.policy import EscalationTarget as T
from app.org.policy import ModelRole
from app.org.policy import Permission as P

CHIEF = "chief_intelligence_agent"


@dataclass(frozen=True)
class EscalationRule:
    condition: E
    target: T
    description: str


DEFAULT_ESCALATIONS = (
    EscalationRule(E.ITERATION_LIMIT, T.MANAGER, "Revision limit reached without passing review."),
    EscalationRule(E.TOOL_FAILURE, T.MANAGER, "A tool or provider call failed."),
    EscalationRule(E.PERMISSION_DENIED, T.HUMAN, "Attempted an action outside its permissions."),
    EscalationRule(E.TASK_BUDGET, T.HUMAN, "The task's execution budget is exhausted."),
    EscalationRule(E.INVALID_OUTPUT, T.MANAGER, "Output failed schema or semantic validation."),
)
LLM_ESCALATIONS = (
    *DEFAULT_ESCALATIONS,
    EscalationRule(E.TOKEN_LIMIT, T.MANAGER, "Input exceeds the agent's token limit."),
    EscalationRule(E.REVIEW_ESCALATED, T.HUMAN, "The reviewer escalated the output."),
)


@dataclass(frozen=True)
class AgentDefinition:
    key: str
    name: str
    role: str
    responsibilities: tuple[str, ...]
    manager: str | None
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    permissions: frozenset[P]
    tools: tuple[str, ...]
    model: ModelRole
    max_input_tokens: int
    max_output_tokens: int
    max_iterations: int
    escalation_rules: tuple[EscalationRule, ...]
    # Phase 1 pipeline agents whose ai_runs count towards this agent's performance.
    pipeline_agents: tuple[str, ...] = field(default=())
    independent: bool = False

    def escalation_target(self, condition: E) -> T:
        for rule in self.escalation_rules:
            if rule.condition == condition:
                return rule.target
        return T.HUMAN


def _agent(**kw) -> AgentDefinition:
    kw["permissions"] = frozenset(kw["permissions"])
    kw["responsibilities"] = tuple(kw["responsibilities"])
    kw["tools"] = tuple(kw["tools"])
    return AgentDefinition(**kw)


RULES_LIMITS = {"max_input_tokens": 0, "max_output_tokens": 0}

AGENTS: dict[str, AgentDefinition] = {
    a.key: a
    for a in [
        _agent(
            key=CHIEF,
            name="Chief Intelligence Agent",
            role="Runs the organization: delegates work along fixed workflows and approves "
            "internal work.",
            responsibilities=[
                "Instantiate the workflow template for each task and delegate steps",
                "Approve internal (non-public) work once every step passed review",
                "Assemble the final task output",
                "Never execute steps itself and never approve externally facing work",
            ],
            manager=None,
            input_schema=S.ChiefInput,
            output_schema=S.DelegationPlan,
            permissions=[P.DELEGATE, P.APPROVE_INTERNAL],
            tools=[],
            model=ModelRole.RULES,
            **RULES_LIMITS,
            max_iterations=1,
            escalation_rules=DEFAULT_ESCALATIONS,
        ),
        _agent(
            key="research_agent",
            name="Research Agent",
            role="Research desk manager: gathers and summarises evidence for claims.",
            responsibilities=[
                "Run the Phase 1 research pipeline (search, evidence, ranking, assessment, "
                "critic) for claims that need it",
                "Summarise searches, sources and evidence by stance",
                "Review the work of the Claim Extraction, Source Verification and Media "
                "Forensics agents",
            ],
            manager=CHIEF,
            input_schema=S.ResearchInput,
            output_schema=S.ResearchOutput,
            permissions=[P.READ_CLAIMS, P.READ_EVIDENCE, P.RUN_PIPELINE, P.REVIEW_WORK],
            tools=["run_claim_pipeline", "read_claim_research"],
            model=ModelRole.RULES,
            **RULES_LIMITS,
            max_iterations=1,
            escalation_rules=DEFAULT_ESCALATIONS,
            pipeline_agents=("evidence_analyst",),
        ),
        _agent(
            key="claim_extraction_agent",
            name="Claim Extraction Agent",
            role="Turns submitted material into atomic, blinded, structured claims.",
            responsibilities=[
                "Extract machine-readable text from the submission",
                "Extract atomic claims (subject, predicate, object, time, place, entities)",
                "Report when a human transcription is needed instead of guessing",
            ],
            manager="research_agent",
            input_schema=S.SubmissionTaskInput,
            output_schema=S.ExtractionOutput,
            permissions=[P.READ_SUBMISSIONS, P.RUN_PIPELINE],
            tools=["extract_submission"],
            model=ModelRole.PRIMARY,
            max_input_tokens=6000,
            max_output_tokens=4096,
            max_iterations=1,
            escalation_rules=LLM_ESCALATIONS,
            pipeline_agents=("claim_extractor",),
        ),
        _agent(
            key="source_verification_agent",
            name="Source Verification Agent",
            role="Checks the provenance and standing of every source behind a claim's evidence.",
            responsibilities=[
                "Look up each source's registry entry, verification and scoped authority",
                "Report primary/secondary status, document quality and age",
                "Flag unregistered, low-authority, outdated or single-origin evidence",
            ],
            manager="research_agent",
            input_schema=S.ClaimTaskInput,
            output_schema=S.SourceVerificationOutput,
            permissions=[P.READ_EVIDENCE, P.READ_REGISTRY],
            tools=["read_claim_research", "read_registry"],
            model=ModelRole.RULES,
            **RULES_LIMITS,
            max_iterations=1,
            escalation_rules=DEFAULT_ESCALATIONS,
        ),
        _agent(
            key="media_forensics_agent",
            name="Media Forensics Agent",
            role="Reports verifiable facts about uploaded media; never claims what it cannot "
            "detect.",
            responsibilities=[
                "Compute file hash, type, size and basic properties",
                "Detect reuse of identical media across submissions",
                "State limitations: no manipulation or deepfake detection, no reverse search",
            ],
            manager="research_agent",
            input_schema=S.SubmissionTaskInput,
            output_schema=S.MediaForensicsOutput,
            permissions=[P.READ_SUBMISSIONS, P.READ_MEDIA],
            tools=["read_media"],
            model=ModelRole.RULES,
            **RULES_LIMITS,
            max_iterations=1,
            escalation_rules=DEFAULT_ESCALATIONS,
        ),
        _agent(
            key="fact_check_agent",
            name="Fact Check Agent",
            role="Verification desk manager: reports fact-check status, never overrides humans.",
            responsibilities=[
                "Report each claim's latest assessment, critic outcome and human review status",
                "Distinguish proposed classifications from human-approved ones",
                "Review the Context Agent's work",
            ],
            manager=CHIEF,
            input_schema=S.FactCheckInput,
            output_schema=S.FactCheckOutput,
            permissions=[P.READ_CLAIMS, P.READ_FACT_CHECKS, P.REVIEW_WORK],
            tools=["read_fact_check"],
            model=ModelRole.RULES,
            **RULES_LIMITS,
            max_iterations=1,
            escalation_rules=DEFAULT_ESCALATIONS,
            pipeline_agents=("assessor",),
        ),
        _agent(
            key="context_agent",
            name="Context Agent",
            role="Explains the context a reader needs, grounded only in retrieved evidence.",
            responsibilities=[
                "Write cited context points from the claim's evidence",
                "List context that is missing from the evidence",
            ],
            manager="fact_check_agent",
            input_schema=S.ClaimTaskInput,
            output_schema=S.ContextOutput,
            permissions=[P.READ_EVIDENCE],
            tools=["read_claim_research"],
            model=ModelRole.PRIMARY,
            max_input_tokens=6000,
            max_output_tokens=1500,
            max_iterations=3,
            escalation_rules=LLM_ESCALATIONS,
        ),
        _agent(
            key="narrative_intelligence_agent",
            name="Narrative Intelligence Agent",
            role="Provides the narrative brief: metrics, recommendation and approved facts.",
            responsibilities=[
                "Refresh the narrative engine and read the narrative's latest metrics",
                "Collect the narrative's human-approved fact-checks",
                "Review the Analytics Agent's work",
            ],
            manager=CHIEF,
            input_schema=S.NarrativeResponseInput,
            output_schema=S.NarrativeBrief,
            permissions=[P.READ_NARRATIVES, P.READ_FACT_CHECKS, P.RUN_ANALYSIS, P.REVIEW_WORK],
            tools=["run_narrative_engine", "read_narrative", "read_approved_facts"],
            model=ModelRole.RULES,
            **RULES_LIMITS,
            max_iterations=1,
            escalation_rules=DEFAULT_ESCALATIONS,
        ),
        _agent(
            key="analytics_agent",
            name="Analytics Agent",
            role="Aggregate statistics only: no individual-level data exists to analyse.",
            responsibilities=[
                "Report claims by classification, review backlog and narrative recommendations",
                "Summarise a narrative's metric trend",
                "Report agent execution volumes",
            ],
            manager="narrative_intelligence_agent",
            input_schema=S.AnalyticsTaskInput,
            output_schema=S.AnalyticsOutput,
            permissions=[P.READ_ANALYTICS],
            tools=["read_analytics"],
            model=ModelRole.RULES,
            **RULES_LIMITS,
            max_iterations=1,
            escalation_rules=DEFAULT_ESCALATIONS,
        ),
        _agent(
            key="response_strategist",
            name="Response Strategist",
            role="Communications desk manager: plans a proportionate, evidence-based response.",
            responsibilities=[
                "Follow the narrative engine's recommendation (it cannot be overridden)",
                "Set objectives, cited key messages, own official channels and format",
                "List what must not be done",
            ],
            manager=CHIEF,
            input_schema=S.NarrativeBrief,
            output_schema=S.StrategyOutput,
            permissions=[P.READ_NARRATIVES, P.READ_FACT_CHECKS, P.REVIEW_WORK],
            tools=[],
            model=ModelRole.PRIMARY,
            max_input_tokens=6000,
            max_output_tokens=1500,
            max_iterations=3,
            escalation_rules=LLM_ESCALATIONS,
        ),
        _agent(
            key="content_agent",
            name="Content Agent",
            role="Drafts evidence-grounded public information; never publishes.",
            responsibilities=[
                "Draft a headline and sentences that each cite an approved fact-check",
                "Use only numbers that appear in the cited fact-checks",
                "Carry the AI-assisted label",
            ],
            manager="response_strategist",
            input_schema=S.StrategyOutput,
            output_schema=S.ContentDraft,
            permissions=[P.READ_FACT_CHECKS, P.DRAFT_CONTENT],
            tools=[],
            model=ModelRole.PRIMARY,
            max_input_tokens=6000,
            max_output_tokens=2000,
            max_iterations=3,
            escalation_rules=(
                *LLM_ESCALATIONS,
                EscalationRule(
                    E.NO_APPROVED_EVIDENCE,
                    T.HUMAN,
                    "No human-approved fact-check to ground content in.",
                ),
            ),
        ),
        _agent(
            key="localization_agent",
            name="Localization Agent",
            role="Translates approved drafts into Indian languages, preserving facts exactly.",
            responsibilities=[
                "Translate the headline and each sentence",
                "Keep every citation and number unchanged",
                "Mark output as machine translation needing fluent human review",
            ],
            manager="response_strategist",
            input_schema=S.ContentDraft,
            output_schema=S.LocalizationOutput,
            permissions=[P.TRANSLATE_CONTENT],
            tools=[],
            model=ModelRole.PRIMARY,
            max_input_tokens=4000,
            max_output_tokens=3000,
            max_iterations=3,
            escalation_rules=LLM_ESCALATIONS,
        ),
        _agent(
            key="critic_agent",
            name="Critic Agent",
            role="Independent reviewer: tries to find errors in other agents' generated work.",
            responsibilities=[
                "Review generated outputs against their source materials",
                "Return PASS, REVISE (with issues) or ESCALATE",
                "Never review its own work",
            ],
            manager=CHIEF,
            input_schema=S.ChiefInput,
            output_schema=S.OrgCritique,
            permissions=[P.REVIEW_WORK, P.READ_EVIDENCE, P.READ_FACT_CHECKS],
            tools=[],
            model=ModelRole.CRITIC,
            max_input_tokens=8000,
            max_output_tokens=1500,
            max_iterations=2,
            escalation_rules=LLM_ESCALATIONS,
            pipeline_agents=("fact_check_critic",),
            independent=True,
        ),
        _agent(
            key="compliance_agent",
            name="Compliance Agent",
            role="Independent gate: blocks drafts that break the platform's rules.",
            responsibilities=[
                "Check the AI-assisted label, citations and number grounding",
                "Block personal data, targeting, impersonation and calls to vote",
                "Block any publish or scheduling instruction",
            ],
            manager=CHIEF,
            input_schema=S.ContentDraft,
            output_schema=S.ComplianceOutput,
            permissions=[P.CHECK_COMPLIANCE, P.READ_FACT_CHECKS],
            tools=[],
            model=ModelRole.RULES,
            **RULES_LIMITS,
            max_iterations=1,
            escalation_rules=(
                *DEFAULT_ESCALATIONS,
                EscalationRule(
                    E.COMPLIANCE_VIOLATION, T.HUMAN, "A draft violates a compliance rule."
                ),
            ),
            independent=True,
        ),
    ]
}


def direct_reports(key: str) -> list[str]:
    return sorted(a.key for a in AGENTS.values() if a.manager == key)


def chain_of_command(key: str) -> list[str]:
    chain, cur = [], AGENTS[key].manager
    while cur:
        chain.append(cur)
        cur = AGENTS[cur].manager
    return chain


def agent_for_pipeline_run(agent_name: str) -> str | None:
    """Organizational owner of a Phase 1 pipeline agent or an org agent key."""
    if agent_name in AGENTS:
        return agent_name
    for a in AGENTS.values():
        if agent_name in a.pipeline_agents:
            return a.key
    return None
