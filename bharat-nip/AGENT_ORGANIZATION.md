# Agent Organization (Phase 3)

A multi-agent organization with fourteen specialised agents, a reporting hierarchy, explicit
workflows, and hard bounds. Agents **never message each other freely**. Work moves only through
workflow templates defined in code, and every handover is a recorded delegation from one step to
the next.

Code: `backend/app/org/`. Version: `org-v1`.

## 1. Principles

| Principle | Enforcement |
|---|---|
| Explicit workflows, no free-form loops | Each task type has a fixed step template (`workflows.py`). Agents cannot create steps, call other agents, or choose who works next. The engine walks the template in order. |
| Bounded | Per-agent `max_iterations` (executions per step, including revisions), a per-task cap (`MAX_EXECUTIONS_PER_TASK = 40`), `MAX_HUMAN_REVISIONS = 2`, and `MAX_STEP_RETRIES = 1` after an escalation. Exceeding any bound escalates. Nothing loops forever. |
| No self-approval | A step's reviewer is never its executor. Task approval is never by an agent that executed a step of the task. External-facing output is approved only by a human REVIEWER+ who did not create the task. |
| Least privilege | Each agent has a permission set and a tool allowlist. Tools check both on every call, and a denied call escalates (`PERMISSION_DENIED`). **No permission or tool exists for publishing, sending, or contacting anyone.** |
| Everything logged | Every delegation, execution, review, revision, escalation and approval is an `org_executions` row (input, output, tool calls, tokens, latency, ai_run link) **and** a hash-chained audit event. |
| Evidence-first | Agents that write content may use only **human-approved** fact-checks. Every sentence must cite one, and every number must appear in the cited fact-check. Speaker identity is never an input. |
| Honest capability | The Media Forensics Agent reports only what it can compute (hashes, file properties, metadata presence, duplicate reuse). It states plainly that it does **not** detect manipulation or deepfakes. |

## 2. Hierarchy

```
Human oversight (admins and reviewers)
└── Chief Intelligence Agent ............. delegates, approves internal work
    ├── Research Agent ................... research desk manager
    │   ├── Claim Extraction Agent
    │   ├── Source Verification Agent
    │   └── Media Forensics Agent
    ├── Fact Check Agent ................. verification desk manager
    │   └── Context Agent
    ├── Narrative Intelligence Agent
    │   └── Analytics Agent
    ├── Response Strategist .............. communications desk manager
    │   ├── Content Agent
    │   └── Localization Agent
    ├── Critic Agent ..................... independent reviewer (reports to the Chief only)
    └── Compliance Agent ................. independent gate (reports to the Chief only)
```

## 3. Agent definition contract

Every agent (`agents.py`) declares: `key`, `name`, `role`, `responsibilities`, `manager`,
`input_schema` and `output_schema` (Pydantic models, exposed as JSON Schema), `permissions`,
`tools`, `model` (`primary` LLM, `critic` LLM, or `rules` = deterministic, no model),
`max_input_tokens`, `max_output_tokens`, `max_iterations`, and `escalation_rules`. The API
(`GET /org/agents`) returns the full definition. Phase 1 pipeline agents are attributed to their
organisational owners for performance: `claim_extractor` → Claim Extraction,
`evidence_analyst` → Research, `assessor` → Fact Check, `fact_check_critic` → Critic.

Escalation conditions (evaluated by the engine, never by agents):
`ITERATION_LIMIT`, `TOKEN_LIMIT`, `REVIEW_ESCALATED`, `COMPLIANCE_VIOLATION`,
`NO_APPROVED_EVIDENCE`, `TOOL_FAILURE`, `PERMISSION_DENIED`, `TASK_BUDGET`, `INVALID_OUTPUT`.
Each rule names a target: `MANAGER` (recorded, then passed up to the human) or `HUMAN`.

## 4. Task lifecycle

```
Task ─▶ delegation ─▶ execution ─▶ review ─▶ (revision ─▶ review)* ─▶ approval ─▶ completion
                                     │                                   │
                                     └──── escalation (bounded) ─────────┴──▶ human
```

1. **Task:** a person (ANALYST+) creates a task of a workflow type with a typed input.
2. **Delegation:** the Chief Intelligence Agent instantiates the template's steps and records one
   `DELEGATION` execution per step (`chief → manager → agent`).
3. **Execution:** each step's agent runs with an input built only from the task input and the
   outputs of declared upstream steps.
4. **Review:** by the step's reviewer: the **Critic Agent** (LLM) for generated content, or the
   agent's **manager** (deterministic acceptance checks) for tool-based work. Outcome PASS,
   REVISE or ESCALATE.
5. **Revision:** REVISE re-runs the same agent with the review feedback, up to the agent's
   `max_iterations`; beyond that the task escalates.
6. **Approval:** `MANAGER`-level workflows (internal analysis) are approved by the Chief after
   deterministic checks. `HUMAN`-level workflows (anything meant for the public) wait in
   `AWAITING_APPROVAL` for a human, who can approve, reject, or request a revision of a named
   step (max 2).
7. **Completion:** the Chief assembles the final output from step outputs.

Task statuses: `PENDING`, `IN_PROGRESS`, `AWAITING_APPROVAL`, `ESCALATED`, `COMPLETED`,
`REJECTED`, `FAILED`, `CANCELLED`. Step statuses: `PENDING`, `RUNNING`, `IN_REVIEW`, `DONE`,
`SKIPPED`, `ESCALATED`, `FAILED`.

## 5. Workflows

| Workflow | Steps (agent → reviewer) | Approval |
|---|---|---|
| `SUBMISSION_FACT_CHECK` | Claim Extraction (content + extraction) → manager; Research (Phase 1 research, assessment and critic for each claim) → manager; Fact Check (status summary) → manager | Chief (internal). Claim verdicts still go through the Phase 1 human review queue. |
| `CLAIM_INVESTIGATION` | Research (run Phase 1 research if needed; summarise) → manager; Source Verification → manager; Context (LLM) → Critic; Fact Check (brief from the latest assessment and human review) → manager | Chief (internal) |
| `MEDIA_CHECK` | Media Forensics → manager (Research) | Chief (internal) |
| `NARRATIVE_RESPONSE` | Narrative Intelligence → manager; Analytics → manager; Response Strategist (LLM) → Critic; Content (LLM) → Critic *(skipped if no public response is recommended)*; Localization (LLM) → Critic *(skipped if no languages are requested or there is no content)*; Compliance (rules) → none (it is the gate) | **Human** (REVIEWER+, not the task creator) |
| `ANALYTICS_REPORT` | Analytics → manager (Narrative Intelligence) | Chief (internal) |

No workflow publishes anything. A completed `NARRATIVE_RESPONSE` is an approved **draft
package** for people to use through the organisation's own, clearly identified channels.

## 6. Content guardrails (Content, Localization, Compliance)

- Content input: approved fact-checks of the narrative's claims, labelled F1..Fn, plus the
  strategist's plan. No approved fact-checks ⇒ `NO_APPROVED_EVIDENCE` (escalate, write nothing).
- Every sentence must cite ≥ 1 valid F-label. Every number in a sentence must appear in a cited
  fact-check's text, so the agent cannot invent statistics.
- Localization must keep each sentence's citations and numbers. Output is marked "machine
  translation: needs a fluent human reviewer".
- Compliance rules (deterministic, `compliance.py`): the AI-assisted label must be present; every
  sentence must be cited; numbers must be grounded; no personal data (emails, phone numbers); no
  demographic or individual targeting language; no impersonation ("I am [name]" style
  first-person attribution to a named person); no calls to vote for or against anyone (fact-check
  communications are not campaign material); no publish or schedule instructions. Any violation
  blocks approval.

## 7. Performance and status (organization view)

Per agent: `status` (`WORKING` if it has a running step, `ESCALATED` if it has an escalated step,
`WAITING` if its work awaits review or approval, else `IDLE`), current task, manager, direct
reports, and performance: executions, success rate, revision rate, escalations, mean latency,
tokens, Phase 1 pipeline runs attributed to it, and its last 5 activities.
