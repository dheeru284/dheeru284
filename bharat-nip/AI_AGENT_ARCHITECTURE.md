# AI Agent Architecture

## 1. Design stance

Agents are **narrow functions with an LLM inside**, not autonomous actors.
Each agent takes a typed input and returns a typed proposal. It has no tools,
no database access and no network access beyond its provider call. A
deterministic orchestrator decides what happens next, and services validate and
persist proposals. This keeps every step testable, bounded and auditable.

```
           ┌──────────── deterministic orchestrator (app/pipeline) ─────────────┐
           │  state table · attempt limits · revision bound · review routing    │
           └──────┬─────────────┬──────────────┬──────────────┬─────────────────┘
                  ▼             ▼              ▼              ▼
          ClaimExtractor  EvidenceAnalyst   Assessor        Critic
                  │             │              │              │
                  └─────────────┴──── LLMProvider ────────────┘
                                         │
                                     ai_runs (every call)
```

## 2. Agents (Milestone 1)

| Agent | `agent_name` | Input | Output schema | Persisted as |
|---|---|---|---|---|
| Claim extractor | `claim_extractor` | submission text, language | `ExtractedClaims{claims:[{text, normalized_text, claim_type, checkworthy}]}` | `claims` |
| Evidence analyst | `evidence_analyst` | blinded claim, list of chunks (id + text) | `EvidenceProposals{items:[{chunk_id, quote, stance, rationale}]}` | `evidence` (after quote verification) |
| Assessor | `assessor` | blinded claim, statement date, ranked evidence (id, quote, stance, score, publisher tier, source type, date) | `AssessmentProposal{verdict, confidence, rationale, missing_context, cited_evidence_ids}` | `assessments`, `assessment_citations` |
| Critic | `critic` | blinded claim, evidence, assessment proposal, verdict definitions | `CritiqueProposal{outcome, checks:[{check, passed, detail}], summary}` | `critiques` |

Not agents: **retrieval** (provider + SQL), **ranking** (deterministic scorer
`rank-v1`), **orchestration** and **review routing** (rules).

## 3. Speaker independence ("attribution blinding")

1. The extractor produces `normalized_text`, in which names of people,
   parties and organizations *making* the claim are replaced with neutral
   placeholders (`[SPEAKER]`, `[ORGANIZATION]`). Entities that are the
   *subject* of a checkable fact stay, because removing them would make the
   claim uncheckable. Example: "[SPEAKER] said the state's GDP grew 9% in 2023".
2. A deterministic post-pass also replaces any known `entities.name` of the
   attributed speaker that remains in `normalized_text`.
3. Assessor and critic prompts are built only from `normalized_text`, the
   statement date and evidence. The prompt builder has no access to
   `speaker_entity_id`. This is enforced by the input schema, which has no
   speaker field.
4. The critic runs an `attribution_leakage` check: does the rationale reason
   from who said it rather than from evidence?
5. **Invariance tests** (see TESTING_STRATEGY) feed the same claim with
   different speakers or parties and require identical normalized text, prompts
   and verdicts.

Evidence *about* a speaker's track record is never used as evidence for a claim.

## 4. Prompts

- Stored at `backend/app/prompts/<prompt_id>/<version>.md`, with front-matter
  (`prompt_id`, `version`, `agent`, `description`).
- Loaded through `PromptRegistry`, which computes `sha256` of the exact file text.
- Rendering uses explicit named variables; untrusted text (submissions,
  source chunks) is wrapped in clearly delimited blocks
  (`<<<SOURCE id=… >>> … <<<END SOURCE>>>`), and the system prompt tells the
  model that text inside these blocks is data, never instructions.
- Any change to prompt text needs a new version file. Old versions stay so
  that historical `ai_runs` stay interpretable.

## 5. Provider abstraction

```python
class LLMProvider(Protocol):
    name: str                         # "ollama", "mock", ...
    def complete(self, request: LLMRequest) -> LLMResponse: ...
    def health(self) -> ProviderHealth: ...

class EmbeddingProvider(Protocol):
    name: str
    dimensions: int
    def embed(self, texts: list[str]) -> EmbeddingResult: ...
    def health(self) -> ProviderHealth: ...
```

- `LLMRequest`: messages, `prompt_id` (lets the mock match scripts; real providers ignore it), temperature, max_tokens, seed, optional
  JSON-schema for structured output.
- `LLMResponse`: text, provider, model, token usage, latency.
- Implementations: `OllamaLLMProvider` (HTTP `/api/chat`, with `format=<json schema>`),
  `MockLLMProvider`. Embeddings: `OllamaEmbeddingProvider` (`/api/embed`),
  `MockEmbeddingProvider`.
- Future `OpenAIProvider`, `AnthropicProvider`, `GeminiProvider` implement the
  same protocol and are added to `providers/registry.py`. Nothing else changes.

### 5.1 The mock provider
`MockLLMProvider` is **test infrastructure**, not a fallback.
- It only returns responses that were explicitly scripted (keyed by
  `prompt_id`, optionally matched on input). An unscripted call raises
  `MockResponseNotScripted`, so it can never invent an answer silently.
- `MockEmbeddingProvider` produces deterministic hash-based vectors. These
  are useful for plumbing tests and meaningless semantically, which is documented in code.
- Settings refuse mock providers outside `BNIP_ENV=test` unless
  `BNIP_ALLOW_MOCK_PROVIDERS=true`, and always in `production`.
- Every mock output is recorded with `provider="mock"`, and the UI badges it.

## 6. The agent call contract (`app/agents/runner.py`, Phase 1)

For every agent call:
1. Render the prompt, then compute `prompt_sha256` and `input_sha256`.
2. Call the provider with `temperature=0` and a fixed seed by default.
3. Parse the output into the agent's Pydantic schema.
4. Record an `ai_runs` row with `status` = `SUCCEEDED` / `INVALID_OUTPUT` / `FAILED`.
5. On `INVALID_OUTPUT`, retry with the validation error appended, up to
   `max_attempts` (default 2) for that call. Each attempt is its own `ai_runs` row.
6. Return the validated proposal or raise `AgentFailed`. The orchestrator then
   marks the job failed or retries the stage.

Step 4 is done by `AIRunRecorder`, which exists in Phase 0, so provenance
recording is in place before any agent ships.

## 7. Guardrails (deterministic, after the agent, before persistence)

| Stage | Guardrail |
|---|---|
| Extraction | ≥1 claim; claim text must be grounded in the submission (token overlap check); `claim_type` in the enum. |
| Evidence | `quote` must be an exact substring of the chunk's source. Offsets are computed by the service, never trusted from the model. `chunk_id` must be one that was offered. Failures are logged as `evidence.rejected` audit events. |
| Assessment | No usable evidence ⇒ `INSUFFICIENT_EVIDENCE`, produced by `RULE` with no LLM call. Cited IDs ⊆ the claim's evidence. Verdicts that need evidence need ≥1 citation. Non-checkable claim types map to `OPINION` / `PREDICTION` / `SATIRE` by rule. |
| Critique | The critic's `agent_name` must differ from the assessment's. The required checks must all be present. |
| Review | Only humans. Reviewer ≠ submitter. One decision per task. |

## 8. Bounded loops and escalation

| Loop | Bound | On exhaustion |
|---|---|---|
| Structured-output retry per agent call | 2 attempts | stage attempt fails |
| Stage attempts (`pipeline_jobs.max_attempts`) | 3 | claim → `FAILED` → review task `STAGE_FAILURE` |
| Assessor ↔ critic revisions | `BNIP_MAX_REVISION_ROUNDS` (2) | review task `LOOP_LIMIT` |
| Critic `ESCALATE` | immediate | review task `CRITIC_ESCALATION` |

An agent never approves its own work. The only terminal "accepted" state,
`APPROVED`, is reachable only through a `review_decisions` row written by a human user.

## 9. Required critic checks (`critic` prompt v1)

`citation_validity`, `verdict_evidence_consistency`, `overclaiming`,
`missing_context`, `attribution_leakage`, `verdict_definition_compliance`,
`insufficient_evidence_honesty` (did the assessor claim certainty that the
evidence can't support?).

## 10. Evaluation (outside CI)

A golden set of claims with human-agreed verdicts (`backend/evals/`, Phase 1d)
is run against real providers to compare models and prompt versions. Results
are stored per prompt version; a prompt version is promoted only if it doesn't
regress verdict agreement or the invariance score.
