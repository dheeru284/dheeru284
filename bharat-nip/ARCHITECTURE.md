# Architecture — Bharat Narrative Intelligence Platform (BNIP)

Status: Phase 2 (narrative intelligence) complete. This document is the source of truth for system
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
          │ LLM provider  │   │ Search providers       │
          │ (Ollama, mock │   │ (local corpus, SearXNG │
          │  future: API) │   │  web search, mock)     │
          └───────────────┘   └────────────────────────┘
```

## 4. Components

### 4.1 Frontend (`frontend/`)
Next.js 16 (App Router, Cache Components), React, TypeScript, Tailwind CSS, shadcn/ui
conventions. Server components call the API with the user's JWT, held in an httpOnly cookie and
never exposed to browser JavaScript; mutations are server actions. React Flow will render the
per-claim pipeline graph (Phase 2) and Recharts aggregate dashboards (Phase 4). The frontend shows only data the backend actually holds:
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
- `llm/`: `LLMProvider` protocol; `OllamaLLMProvider`, `MockLLMProvider` (scripted).
- `embeddings/`: `EmbeddingProvider` protocol; `OllamaEmbeddingProvider`, `MockEmbeddingProvider`.
- `search/`: `SearchProvider` protocol; `LocalCorpusSearchProvider` (PostgreSQL full-text over
  ingested sources), `SearxngSearchProvider` (configurable web search via self-hosted SearXNG),
  `MockSearchProvider` (scripted).
- `fixtures.py`: loads scripted mock responses from JSON for local demos (never in production).

Future OpenAI / Anthropic / Gemini / commercial-search providers implement the same protocols and
are registered in `providers/registry.py`. No stub classes are created before they are implemented.

### 4.6a Ingestion (`backend/app/ingest`)
`SafeFetcher` (SSRF-protected HTTP: scheme allowlist, every hop resolved and checked against
private ranges, manual redirects, size and time limits) and extractors for HTML (title,
publisher, publication date, main text), PDF text layers (pypdf), and optional OCR (local
`tesseract` if installed). Uploaded files are type-sniffed from their bytes and stored by sha256.

### 4.6b Narrative intelligence (`backend/app/narratives`)
Built on the verified evidence layer ([NARRATIVE_INTELLIGENCE.md](NARRATIVE_INTELLIGENCE.md)).
Pure modules: `similarity.py` (TF-IDF over blinded text), `metrics.py`, `recommend.py`
(`rec-v1`, plus the status transition table). The DB-touching `engine.py` runs under an advisory
lock and is idempotent. `service.py` holds analyst operations; `queries.py` holds read models
(claim history, evidence timeline, graph, historical matching). The engine never reads speaker
identity and never changes a narrative's status.

### 4.7 Audit (`backend/app/audit`)
`AuditService.record(...)` appends a hash-chained event inside the caller's
transaction, so the domain change and its audit event commit or roll back
together. `AuditService.verify_chain()` recomputes the chain.

### 4.8 Workers (`backend/app/workers`)
Celery app with Redis as broker and result backend. Tasks are idempotent per
`pipeline_jobs.id` and delegate to services.

## 5. Milestone 1 data flow (implemented)

```
POST /submissions (text, URL, article, image, PDF, video metadata)   audit: submission.created
  ▼
[CONTENT]      text from user input, fetched page (HTML/PDF), PDF text layer, OCR, or a human
               transcription; none available ⇒ NEEDS_TRANSCRIPTION (never guessed)
  ▼
[EXTRACTION]   claim_extractor → atomic claims (subject/predicate/object, time, location,
               entities, original source); grounding check; speaker blinding
  ▼  per claim:
[SEARCH]       every configured SearchProvider × deterministic queries from the blinded claim →
               search_queries/results; hits fetched (SafeFetcher) or provided → immutable sources
  ▼
[EVIDENCE]     top passages (lexical relevance) → evidence_analyst → verbatim quote located in
               the stored source → evidence (stance, directness, relevance)
  ▼
[RANKING]      rank-v2: authority, primary source, relevance, recency, directness,
               corroboration, document quality → evidence_rankings
  ▼
[ASSESSMENT]   rules first (non-checkable ⇒ OPINION/PREDICTION/SATIRE; no evidence ⇒
               INSUFFICIENT_EVIDENCE, no LLM); else assessor + validation + confidence calibration
  ▼
[CRITIQUE]     fact_check_critic (independent) + deterministic findings → PASS / REVISE / ESCALATE
               REVISE ⇒ ASSESSMENT again (≤ BNIP_MAX_REVISION_ROUNDS), then LOOP_LIMIT
  ▼
[REVIEW_ROUTING] review task (always) → PENDING_REVIEW
  ▼
human decision: APPROVED / REJECTED / NEEDS_MORE_RESEARCH (→ re-research → new revision)
```
Every stage is a `pipeline_jobs` row, every LLM call an `ai_runs` row, and every state change an
audit event. A failing stage keeps its records and sends the claim to a human (`STAGE_FAILURE`).
Rule-produced assessments skip the critic (there is no agent reasoning to challenge) but still
go to a human.

## 6. Repository layout

```
bharat-nip/
├── *.md                      design documents
├── docker-compose.yml        postgres+pgvector, redis, optional ollama
├── infra/                    database init script
├── Makefile                  developer commands
├── backend/
│   ├── pyproject.toml, uv.lock
│   ├── alembic/versions/     0001 baseline, 0002 phase 1
│   ├── fixtures/             fictional mock fixtures for local demos
│   ├── app/
│   │   ├── main.py           FastAPI app factory
│   │   ├── cli.py            create-user, seed-demo
│   │   ├── core/             config, security (Argon2, JWT), hashing, logging
│   │   ├── db/               engine, session, base
│   │   ├── domain/           enums, claim state machine, text utilities (blinding, relevance, chunking, quote location)
│   │   ├── models/           SQLAlchemy models
│   │   ├── schemas/          Pydantic API schemas
│   │   ├── api/              routers, auth dependencies, access rules, problem+json
│   │   ├── services/         submissions, content, extraction, registry, sources, research,
│   │   │                     ranking, assessment, critic, review, factcheck, users, storage
│   │   ├── pipeline/         orchestrator, context, dispatch (Celery / inline)
│   │   ├── agents/           agent runner and definitions
│   │   ├── ai/               PromptRegistry, AIRunRecorder
│   │   ├── prompts/          claim_extractor, evidence_analyst, assessor, fact_check_critic (v1)
│   │   ├── providers/        llm / embeddings / search / fixtures / registry
│   │   ├── ingest/           SafeFetcher, HTML/PDF/OCR extraction
│   │   ├── narratives/       narrative engine, metrics, recommendation, queries
│   │   ├── audit/            hash-chained audit service
│   │   └── workers/          Celery app and tasks
│   └── tests/
└── frontend/                 Next.js: login, submit, submissions, claims, claim detail, review,
                              narratives dashboard/detail/graph
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
| `BNIP_ALLOW_MOCK_PROVIDERS` | `false` | Must be `true` to use any mock provider (LLM, embeddings, search) outside `test`. In `production`, mocks are refused regardless. |
| `BNIP_OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `BNIP_OLLAMA_MODEL` | `llama3.1:8b` | |
| `BNIP_OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Must produce 768-dim vectors |
| `BNIP_OLLAMA_CRITIC_MODEL` | (same as `BNIP_OLLAMA_MODEL`) | Optional separate model for the critic |
| `BNIP_MAX_REVISION_ROUNDS` | `2` | Assessor↔critic loop bound |
| `BNIP_SEARCH_PROVIDERS` | `["local_corpus"]` | Any of `local_corpus`, `searxng`, `mock` |
| `BNIP_SEARXNG_URL` | — | Required when `searxng` is enabled |
| `BNIP_FETCH_ALLOW_HTTP` | `false` | HTTPS-only fetching by default |
| `BNIP_FETCH_MAX_BYTES` / `BNIP_FETCH_TIMEOUT_SECONDS` | `5000000` / `15` | Fetch limits |
| `BNIP_STORAGE_DIR` | `backend/storage` | Uploaded files |
| `BNIP_PIPELINE_EXECUTION` | `celery` | `celery` or `inline` |
| `BNIP_NARRATIVE_INTERVAL_MINUTES` | `15` | Celery beat interval for the narrative engine (`make dev-beat`) |
| `BNIP_MOCK_FIXTURES_PATH` | — | Scripted mock responses (non-production) |
| `BNIP_JWT_SECRET` / `BNIP_JWT_EXPIRY_MINUTES` | dev secret / `60` | The secret is required (≥32 chars) in production |

## 9. Runnability guarantee

After each phase, the following must pass from a clean checkout (see
[TESTING_STRATEGY](TESTING_STRATEGY.md)):

```
make backend-install frontend-install migrate
make check          # backend lint + tests, frontend lint + typecheck + tests + build
```
