# AI Agent Architecture

## 1. Design stance

Agents are **narrow functions with an LLM inside**, not autonomous actors. Each takes a typed
input (a rendered, versioned prompt) and returns a typed proposal. Agents have no tools, no
database access and no network access beyond their provider call. A deterministic orchestrator
decides what happens next, and services validate proposals before persisting them.

```
        deterministic orchestrator (app/pipeline/orchestrator.py)
        stage jobs · attempt limits · revision bound · review routing
           │            │                 │              │
   ClaimExtractor  EvidenceAnalyst     Assessor   FactCheckCriticAgent
           └────────────┴────── LLMProvider ─────────────┘
                                   │
                         ai_runs + audit (every attempt)
```

## 2. Agents (Phase 1)

| Agent (`agent_name`) | Prompt | Input | Output | Persisted after validation as |
|---|---|---|---|---|
| `claim_extractor` | `claim_extractor/v1` | submission text (as a data block), language, speaker name for blinding | claims: text, normalized_text, subject/predicate/object, claim_type, checkworthy, time_reference, claim_date, location, entities | `claims` |
| `evidence_analyst` | `evidence_analyst/v1` | blinded claim, top passages labelled C1..Cn | items: passage label, verbatim quote, stance, directness, relevance, rationale | `evidence` |
| `assessor` | `assessor/v1` | blinded claim, time/place, statement date, ranked evidence labelled E1..En (stance, directness, rank score, authority, primary, date, quote) and, on revision, the critic's objections | classification, confidence, summary, reasoning, cited labels, missing information, recommended action | `assessments` + citations |
| `fact_check_critic` | `fact_check_critic/v1` | blinded claim, the proposed assessment (output only), ALL usable evidence, deterministic findings | outcome, 8 checks, counter-argument, suggested classification, summary | `critiques` |

Not agents: **search** (providers + SQL), **source snapshotting**, **ranking** (`rank-v2`),
**confidence calibration**, **deterministic critic findings**, **orchestration** and **review
routing**. These are all plain, tested code.

Labels (C1, E1, ...) are local to one prompt. The model never sees or emits database IDs, and
services map labels back to IDs. An unknown label is invalid output.

## 3. Speaker independence ("attribution blinding")

1. The extractor writes `normalized_text` with the claim's maker replaced by `[SPEAKER]`.
   Entities the claim is *about* stay.
2. A deterministic post-pass (`app/domain/text.py::blind`) replaces any remaining SPEAKER-role
   entity name, and the submission's speaker entity name (case-insensitive, whole words, possessives).
3. Search queries are built from the blinded text and the triple only (`build_queries`), so the
   speaker never reaches a search engine.
4. Assessor and critic prompts are built only from `normalized_text`, time, place, statement date
   and evidence. There is no speaker field to fill.
5. The critic checks `attribution_leakage`.
6. **Invariance test** (`tests/test_invariance.py`): the same claim from three fictional speakers of
   different parties yields identical blinded text, an identical assessor input hash
   (`ai_runs.input_sha256`) and the same classification, and no name or party appears in any
   assessor message.

## 4. Prompts

`backend/app/prompts/<prompt_id>/<version>.md`: YAML front-matter (`prompt_id`, `version`,
`agent`, `description`), the system prompt, a `@@USER@@` marker line, and the user template.
`PromptRegistry` hashes the exact file bytes (`ai_runs.prompt_sha256`). Rendering is strict (no
missing or extra variables) and doesn't re-expand values. Untrusted text is wrapped by
`wrap_untrusted` in `<<<KIND id=…>>> … <<<END KIND>>>` blocks, with look-alike delimiters
neutralised. Prompt text is never edited in place: changes go in a new version file.

## 5. Providers

```python
class LLMProvider(Protocol):        # name, model, is_mock; complete(LLMRequest); health()
class EmbeddingProvider(Protocol):  # name, model, dimensions, is_mock; embed(texts); health()
class SearchProvider(Protocol):     # name, is_mock; search(query, limit, *, session); health()
```

| Kind | Implementations | Selected by |
|---|---|---|
| LLM | `OllamaLLMProvider` (`/api/chat`, JSON-schema `format`, seed, temperature 0), `MockLLMProvider` | `BNIP_LLM_PROVIDER` |
| Critic LLM | same provider; optionally a different Ollama model for independence | `BNIP_OLLAMA_CRITIC_MODEL` |
| Embeddings | `OllamaEmbeddingProvider`, `MockEmbeddingProvider` | `BNIP_EMBEDDING_PROVIDER` |
| Search | `LocalCorpusSearchProvider` (PostgreSQL full-text over ingested sources), `SearxngSearchProvider` (configurable web search via a self-hosted SearXNG), `MockSearchProvider` | `BNIP_SEARCH_PROVIDERS` (list; all are queried) |

A search hit is either a URL, which the pipeline fetches through `SafeFetcher` (SSRF-protected)
and snapshots, or content the provider already holds verbatim (local corpus, mock). Search
providers cannot create sources themselves. Future OpenAI / Anthropic / Gemini / Brave providers
implement the same protocols and are registered in `providers/registry.py`.

### 5.1 Mock providers
`MockLLMProvider` and `MockSearchProvider` are **test infrastructure**. They return only
explicitly scripted responses and raise on anything unscripted. A scripted response may be a
function of the request: tests use this to find which passage label holds a known document.
`BNIP_MOCK_FIXTURES_PATH` loads scripts from JSON for local demos (`backend/fixtures/demo_mock.json`,
entirely fictional). Settings refuse mocks and fixtures in production, and in development without
`BNIP_ALLOW_MOCK_PROVIDERS=true`. Every mock output is recorded with `provider="mock"`, and the UI
shows a MOCK badge.

## 6. The agent call contract (`app/agents/runner.py`)

render → `provider.complete` (schema-constrained) → parse JSON → Pydantic validation → semantic
validation → `AIRunRecorder.record` (one `ai_runs` row and one `ai_run.recorded` audit event per
attempt) → on invalid output, retry with the error appended, up to 2 attempts → validated output
or `AgentFailed`. Provider failures are recorded as `FAILED` runs and are never retried silently.

## 7. Guardrails (deterministic)

| Stage | Guardrail |
|---|---|
| Content | No machine-readable text (image without OCR, scanned PDF) ⇒ `NEEDS_TRANSCRIPTION`; the system never guesses text. |
| Extraction | Claims must be grounded in the material (content-term overlap ≥ 0.5) and are de-duplicated. Rejections are audited. |
| Search | The claim's own original URL is skipped (not independent evidence). Every query and result is recorded. |
| Evidence | Passage labels must be ones offered. The quote is located verbatim (exact, or identical words with only whitespace differences); the stored quote is the source's own slice. Anything else is rejected and audited. |
| Assessment | Non-checkable types ⇒ OPINION / PREDICTION / SATIRE by rule. No usable evidence ⇒ `INSUFFICIENT_EVIDENCE` by rule with **no LLM call**. Cited labels must exist. TRUE/MOSTLY_TRUE must cite a SUPPORTS item; FALSE must cite a REFUTES item; affirmative classifications need ≥1 citation. The assessor may not output OPINION/PREDICTION/SATIRE. |
| Calibration | Confidence caps, recorded in `guardrails`: non-determination ≤ 0.5; fewer than 2 independent origins ≤ 0.6; no primary source ≤ 0.75; only unassessed/limited authority ≤ 0.6; high-ranked contrary evidence ≤ 0.5. |
| Critique | Critic identity ≠ assessor identity (`SelfReviewError`). All 8 checks exactly once; PASS only if every check passed. A critic PASS with a HIGH deterministic finding becomes ESCALATE (`RULE_FLAG`). |
| Review | Only humans decide. Reviewer ≠ submitter. One decision per task. Notes required for REJECT, NEEDS_MORE_RESEARCH, or changing the classification. |

### 7.1 Deterministic critic findings
`contradictory_evidence` (HIGH: uncited opposite-stance evidence with rank ≥ 0.5),
`outdated_evidence` (MEDIUM: cited evidence > 5 years older than the claim's reference date),
`source_quality` (MEDIUM: single origin, or only unassessed/limited authority),
`unsupported_conclusions` (HIGH: confidence > 0.7 while the best cited rank is < 0.4).

## 8. Bounded loops and escalation

| Loop | Bound | On exhaustion |
|---|---|---|
| Invalid-output retry per agent call | 2 attempts | stage fails |
| Stage retry (transient provider errors only) | 2 attempts | claim `FAILED` → review `STAGE_FAILURE` |
| Assessor ↔ critic revisions | `BNIP_MAX_REVISION_ROUNDS` (default 2) | review `LOOP_LIMIT` |
| Critic `ESCALATE` | immediate | review `CRITIC_ESCALATION` (or `RULE_FLAG` if overridden) |

## 9. Evaluation (outside CI)

A golden set of claims with human-agreed classifications is planned for Phase 2. It will be run
against real providers per prompt version, and a prompt version is promoted only if it doesn't
regress agreement or invariance.
