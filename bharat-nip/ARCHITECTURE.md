# Architecture — Bharat Narrative Intelligence Platform (BNIP)

Status: Phase 0 (foundation). This document is the source of truth for system
structure. If code and this document disagree, fix one of them in the same change.

Related documents: [PRODUCT_REQUIREMENTS](PRODUCT_REQUIREMENTS.md) ·
[DATABASE_DESIGN](DATABASE_DESIGN.md) · [AI_AGENT_ARCHITECTURE](AI_AGENT_ARCHITECTURE.md) ·
[API_DESIGN](API_DESIGN.md) · [TESTING_STRATEGY](TESTING_STRATEGY.md) ·
[SECURITY](SECURITY.md) · [ROADMAP](ROADMAP.md)

## 1. Purpose

BNIP is an evidence-first platform for political information, fact-checking,
narrative intelligence and legitimate public communications. Its core is a
**claim-assessment pipeline** that evaluates claims on evidence alone,
independent of who made them.

## 2. Architectural principles

| Principle | How the architecture enforces it |
|---|---|
| Speaker-independent assessment | The assessor and critic agents receive a *blinded* claim (speaker, party and organization removed). Attribution is stored separately and never enters assessment prompts. Invariance tests swap speakers and require identical verdicts. |
| No fabricated sources | A `source` row can only be created by a retrieval provider or a human ingest, with a stored content snapshot and SHA-256 hash. LLMs have no write path to `sources`. |
| No fabricated evidence | Every evidence quote must be an exact substring of a stored source snapshot; offsets are verified mechanically before the row is saved. |
| Traceability | Every assessment cites evidence IDs; every evidence row points to a source chunk; every AI output links to an `ai_run`. |
| AI provenance | Every LLM call is recorded in `ai_runs` with provider, model, prompt ID, prompt version and prompt hash. |
| No self-approval | Assessor ≠ critic (enforced by agent identity check). An agent can never set a final status. Only a human reviewer can approve, and not on a submission they made themselves. |
| Bounded loops | The assessor↔critic revision loop has a hard limit (default 2 revisions). Hitting it escalates to a human. |
| Human oversight | In Milestone 1, **every** assessment goes to human review before it is final. |
| Audit trail | Append-only, hash-chained `audit_events` table; DB trigger blocks UPDATE/DELETE/TRUNCATE. |
| Provider independence | LLM, embedding and source retrieval sit behind Python protocols, selected by configuration. |

## 3. System context

```
                  ┌──────────────────────────────┐
  Analysts,       │  Next.js web app (frontend/) │
  reviewers  ───▶ │  React, TS, Tailwind, shadcn │
  admins          └──────────────┬───────────────┘
                                 │ HTTPS / JSON (REST, /api/v1)
                  ┌──────────────▼───────────────┐
                  │  FastAPI app (backend/app)   │
                  │  - API routes / auth / RBAC  │
                  │  - domain services           │
                  │  - audit service             │
                  └───┬─────────────┬────────────┘
         SQLAlchemy   │             │ enqueue (Celery)
                  ┌───▼────────┐ ┌──▼──────┐
                  │ PostgreSQL │ │  Redis  │
                  │ + pgvector │ │ broker  │
                  └───▲────────┘ └──┬──────┘
                      │             │ consume
                  ┌───┴─────────────▼────────────┐
                  │  Celery workers              │
                  │  - pipeline stage tasks      │
                  │  - agents (via providers)    │
                  └───┬───────────────┬──────────┘
                      │               │
          ┌───────────▼───┐   ┌───────▼────────────────┐
          │ LLM provider  │   │ Source retrieval       │
          │ (Ollama, mock │   │ provider (local corpus │
          │  future: API) │   │  first; web later)     │
          └───────────────┘   └────────────────────────┘
```

## 4. Components

### 4.1 Frontend (`frontend/`)
Next.js (App Router), React, TypeScript, Tailwind CSS, shadcn/ui. React Flow
renders the per-claim pipeline graph (Phase 2); Recharts renders aggregate
dashboards (Phase 4). The frontend shows only data the backend actually holds:
no placeholder verdicts, no simulated progress. Any output produced by the
mock provider carries a visible "MOCK" badge.

### 4.2 API (`backend/app/api`)
FastAPI routers under `/api/v1`. Routes are thin: validate input with Pydantic,
call a service, return a schema. See [API_DESIGN](API_DESIGN.md).

### 4.3 Domain services (`backend/app/services`)
Plain Python functions/classes taking a SQLAlchemy `Session`. They hold all
business rules (state transitions, four-eyes rule, quote verification). They are
called by both API routes and Celery tasks, so they are testable without either.

### 4.4 Pipeline orchestrator (`backend/app/pipeline`)
A **deterministic state machine**, not an LLM. It decides the next stage from
the claim status and stage results, enqueues Celery tasks, enforces attempt and
loop limits, and routes to human review. Each stage execution is a
`pipeline_jobs` row.

### 4.5 Agents (`backend/app/agents`)
Narrow, single-purpose LLM roles (extractor, evidence analyst, assessor,
critic). Each has a versioned prompt, a Pydantic output schema, and no side
effects: agents return structured proposals; services validate and persist
them. See [AI_AGENT_ARCHITECTURE](AI_AGENT_ARCHITECTURE.md).

### 4.6 Providers (`backend/app/providers`)
- `llm/`: `LLMProvider` protocol; `OllamaLLMProvider`, `MockLLMProvider`.
- `embeddings/`: `EmbeddingProvider` protocol; `OllamaEmbeddingProvider`, `MockEmbeddingProvider`.
- `retrieval/`: `SourceRetrievalProvider` protocol; `LocalCorpusProvider` (Phase 1).

Future OpenAI / Anthropic / Gemini providers implement the same protocol and
are registered in `providers/registry.py`. No stub classes are created for them
until they are implemented.

### 4.7 Audit (`backend/app/audit`)
`AuditService.record(...)` appends a hash-chained event inside the caller's
transaction, so the domain change and its audit event commit or roll back
together. `AuditService.verify_chain()` recomputes the chain.

### 4.8 Workers (`backend/app/workers`)
Celery app with Redis as broker and result backend. Tasks are idempotent per
`pipeline_jobs.id` and delegate to services.

## 5. Milestone 1 data flow

```
POST /submissions
  │  (audit: submission.created)
  ▼
[EXTRACTION]   ClaimExtractor agent → claims (type: FACTUAL / OPINION / PREDICTION / SATIRE / UNCLEAR)
  ▼
[RETRIEVAL]    LocalCorpusProvider: vector + keyword search over source_chunks → retrieval_results
  ▼
[EVIDENCE]     EvidenceAnalyst agent proposes (chunk, quote, stance);
               service verifies the quote is an exact substring → evidence
  ▼
[RANKING]      Deterministic, versioned scorer → evidence_rankings
  ▼
[ASSESSMENT]   Assessor agent (blinded claim + ranked evidence) → assessment + citations
               guardrails: no evidence ⇒ INSUFFICIENT_EVIDENCE; citations must be this claim's evidence
  ▼
[CRITIQUE]     Critic agent (different identity) → PASS / REVISE / ESCALATE
               REVISE ⇒ back to ASSESSMENT (max 2 revisions), then ESCALATE
  ▼
[REVIEW]       review_task (always, in M1) → human decision APPROVE / AMEND / REJECT / REQUEST_MORE_EVIDENCE
  ▼
claim APPROVED / REJECTED     (every transition writes an audit event)
```

Non-checkable claims (OPINION, PREDICTION, SATIRE) skip retrieval and evidence.
They get an assessment with the matching verdict straight from classification,
then go through critique and human review like any other claim.

## 6. Repository layout

```
bharat-nip/
├── *.md                      design documents
├── docker-compose.yml        postgres+pgvector, redis, optional ollama
├── infra/                    database init script
├── Makefile                  common developer commands
├── .env.example
├── backend/
│   ├── pyproject.toml        uv-managed
│   ├── alembic.ini, alembic/ migrations
│   ├── app/
│   │   ├── main.py           FastAPI app factory
│   │   ├── core/             config, logging, hashing
│   │   ├── db/               engine, session, base
│   │   ├── domain/           enums and shared value types
│   │   ├── models/           SQLAlchemy models
│   │   ├── schemas/          Pydantic API schemas
│   │   ├── api/              routers
│   │   ├── services/         business logic
│   │   ├── pipeline/         state machine (Phase 1)
│   │   ├── agents/           agent definitions (Phase 1)
│   │   ├── ai/               PromptRegistry, AIRunRecorder
│   │   ├── prompts/          versioned prompt files
│   │   ├── providers/        llm / embeddings / retrieval
│   │   ├── audit/            audit service
│   │   └── workers/          Celery app and tasks
│   └── tests/
└── frontend/                 Next.js app
```

## 7. Key technology decisions

| Decision | Choice | Why |
|---|---|---|
| DB access | SQLAlchemy 2.x, **synchronous**, psycopg 3 | Same code path for API and Celery workers; simpler tests. Revisit only if API latency demands async. |
| Enums in DB | `VARCHAR` + `CHECK` constraint (non-native enums) | Adding a value is a simple migration; no `ALTER TYPE` pain. |
| IDs | UUIDv4 primary keys; `audit_events` uses a bigint sequence | Non-guessable IDs; audit needs strict ordering. |
| Job system | Celery + Redis | Mature retries, visibility and routing. Tasks are thin wrappers over services. |
| Vector dims | 768 (`nomic-embed-text` via Ollama) | Free, local. Changing the model requires a migration and re-embed; `embedding_model` is stored per chunk. |
| Prompts | Files in the repo (`app/prompts/<agent>/<version>.md`), hashed at load | Git history *is* the prompt history; the hash in `ai_runs` proves which text ran. |
| Auth (M1) | Local accounts, Argon2 password hashing, short-lived JWT | No external dependency for development; OIDC planned in Phase 3. |
| Package mgmt | `uv` (backend), `npm` (frontend) | Fast, lockfile-based, reproducible. |

## 8. Runtime configuration

All configuration comes from environment variables (prefix `BNIP_`), loaded by
`app/core/config.py` (pydantic-settings). See `.env.example`. Important ones:

| Variable | Default | Notes |
|---|---|---|
| `BNIP_ENV` | `development` | `development`, `test`, `production` |
| `BNIP_DATABASE_URL` | `postgresql+psycopg://bnip:bnip@localhost:5432/bnip` | |
| `BNIP_REDIS_URL` | `redis://localhost:6379/0` | |
| `BNIP_LLM_PROVIDER` | `ollama` | `ollama` or `mock` |
| `BNIP_EMBEDDING_PROVIDER` | `ollama` | `ollama` or `mock` |
| `BNIP_ALLOW_MOCK_PROVIDERS` | `false` | Must be `true` to use a mock provider outside `test`. In `production`, mock providers are refused regardless. |
| `BNIP_OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `BNIP_OLLAMA_MODEL` | `llama3.1:8b` | |
| `BNIP_OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Must produce 768-dim vectors |
| `BNIP_MAX_REVISION_ROUNDS` | `2` | Assessor↔critic loop bound |

## 9. Runnability guarantee

After each phase, the following must pass from a clean checkout (see
[TESTING_STRATEGY](TESTING_STRATEGY.md)):

```
make backend-install frontend-install migrate
make check          # backend lint + tests, frontend lint + typecheck + tests + build
```
