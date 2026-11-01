# Roadmap

Each phase ends with a runnable application, green tests, reproducible
migrations and updated docs. A phase doesn't start until the previous one meets
its exit criteria ([TESTING_STRATEGY](TESTING_STRATEGY.md) §6).

## Phase 0 — Foundation ✅ (this change)
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

## Phase 1 — Milestone 1: evidence pipeline (backend)
- **1a Submission and extraction:** auth and RBAC, users, submissions API, Celery
  orchestration, `claim_extractor` agent v1, blinding post-pass, audit events.
- **1b Sources and evidence:** entities and publishers APIs, source ingest with
  chunking and embeddings, `LocalCorpusProvider` hybrid retrieval,
  `evidence_analyst` agent v1 with quote verification.
- **1c Ranking and assessment:** `rank-v1` scorer, `assessor` agent v1 with guardrails.
- **1d Critic and human review:** `critic` agent v1, bounded revision loop,
  review-task routing, review API with the four-eyes rule, audit verification
  endpoint, invariance test suite, golden-set eval harness.

Exit: the full pipeline end-to-end in CI with the mock provider, and manually with Ollama.

## Phase 2 — Milestone 1 UI
Submission form, claims list, claim detail with a React Flow pipeline graph,
evidence and provenance view, review queue and decision screen, audit viewer.
Playwright E2E for submit → review.

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
