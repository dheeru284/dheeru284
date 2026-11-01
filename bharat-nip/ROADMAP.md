# Roadmap

Each phase ends with a runnable application, green tests, reproducible
migrations and updated docs. A phase doesn't start until the previous one meets
its exit criteria ([TESTING_STRATEGY](TESTING_STRATEGY.md) §6).

## Phase 0 — Foundation ✅
- Design documents (the eight in this folder).
- Backend skeleton: FastAPI app factory, settings with mock-provider guards,
  SQLAlchemy models for the full Milestone 1 schema, initial Alembic migration
  (pgvector, CHECK constraints, append-only audit trigger).
- Domain enums and the claim state-transition table.
- Provider layer: `LLMProvider` / `EmbeddingProvider` protocols; Ollama and mock
  implementations; registry.
- `PromptRegistry` (versioned, hashed prompt files) and `AIRunRecorder`.
- `AuditService` with hash chain and verification.
- Celery app with a health task.
- System endpoints: `/health`, `/health/ready`, `/system/providers`.
- Next.js frontend skeleton showing **live** backend readiness.
- docker-compose, Makefile, CI workflow.

Phase 0 notes:
- shadcn/ui is configured (`components.json`); the first two components were
  hand-written to its conventions because the registry was unreachable from the build sandbox.
- React Flow and Recharts are deliberately not installed yet; they arrive with
  the screens that use them (Phases 2 and 4).
- `docker-compose.yml` has not been exercised in the build sandbox (no Docker
  daemon there). Development used host-installed Postgres 16 + pgvector 0.6 and Redis 7.

## Phase 1 — Milestone 1: evidence pipeline ✅
- Auth (Argon2 + JWT), roles, object-level access, admin CLI.
- Submission of text, URL (SSRF-safe fetch), article, image, PDF and video metadata; byte-sniffed
  uploads; human transcription when there is no machine-readable text.
- Claim extraction into structured, blinded, grounded claims.
- Source registry (scoped, verified, expiring authority; not a true/false list).
- `SearchProvider` abstraction: mock, SearXNG (configurable web search), local corpus.
- Evidence with verbatim-quote verification; `rank-v2` seven-factor ranking.
- Assessment with rules, validation and confidence calibration; structured fact-check result.
- Independent `FactCheckCriticAgent` with deterministic findings and enforced overrides; bounded revision loop.
- Human review (PENDING_REVIEW / APPROVED / REJECTED / NEEDS_MORE_RESEARCH) with the four-eyes rule; re-research.
- Audit events for every step, including agent executions.
- Celery orchestration with per-stage jobs; inline mode for tests.
- Web UI: sign in, submit (all types), submission and claim pages with result, evidence, critic,
  searches, stages and audit trail, review queue and decision form.
- 132 backend tests, including HTTP and service-level end-to-end tests with mocks only.

Phase 1 notes and known limits:
- OCR needs `tesseract` on the server. Without it, image submissions ask for a transcription.
- Embeddings are not populated yet; retrieval is lexical (full-text) plus agent relevance.
- SearXNG integration is tested against a mocked HTTP transport; a live instance has not been
  exercised in the build sandbox.
- No live Ollama run happened in the build sandbox (no model server there). The Ollama provider
  is contract-tested with a mocked transport.

## Phase 2 — Retrieval quality, evaluation and UI depth
Embeddings and hybrid retrieval, a golden-set evaluation harness with live Ollama runs, a React
Flow pipeline graph, registry/source management screens, an audit viewer, and Playwright E2E in CI.

## Phase 3 — Hardening
OIDC SSO, rate limiting, DB role separation for audit, structured logging and
metrics (OpenTelemetry), dependency auditing, backup and restore runbook,
external anchoring of the audit chain head.

## Phase 4 — Narrative intelligence
Cluster approved claims into narratives (embedding similarity plus human
curation). Track narrative volume over time across ingested *public* sources.
Recharts dashboards. Aggregate only; no individual tracking.

## Phase 5 — Communications support
Evidence-grounded drafts (explainers, corrections, briefs) generated **only**
from approved assessments. Every sentence must map to a citation, verified by
the same guardrails. Drafts are labeled AI-assisted and need human approval.
A separate critic checks accuracy and tone.

## Phase 6 — Publishing integrations (gated)
Only after Phases 1–5 are proven in production. Publishing to the
organization's own, clearly-identified official accounts, with human approval
per post, a full audit trail, and none of the prohibited capabilities in
[SECURITY](SECURITY.md) §5.

## Later / under consideration
- Indic-language support (Hindi first) for extraction, retrieval and assessment.
- Additional LLM providers (OpenAI, Anthropic, Gemini) behind the existing protocol.
- Web and news retrieval providers, under the SSRF controls.
- Re-checking `PREDICTION` claims when their date passes.
