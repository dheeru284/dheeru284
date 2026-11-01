# CLAUDE.md — Bharat Narrative Intelligence Platform (BNIP)

Guidance for Claude Code when working inside `bharat-nip/`. You are acting as lead engineer.

## What this is

An evidence-first political information, fact-checking, narrative-intelligence and
communications platform. Read [README.md](README.md), then the design docs it lists.
**The design docs are the source of truth.** If code and docs disagree, fix one of
them in the same change.

Current phase: **Phase 0 complete** (foundation). Next: Phase 1a in [ROADMAP.md](ROADMAP.md).

## Non-negotiable rules

1. Assess claims on evidence only. Never let speaker, party, ideology, nationality
   or organization influence a verdict, ranking or reliability tier. Assessor and
   critic only ever see `claims.normalized_text` (blinded).
2. Never fabricate sources, evidence, quotes or statistics. Sources come only from
   retrieval providers or human ingest. Evidence quotes must be exact substrings of
   stored snapshots.
3. When evidence is insufficient, say so (`INSUFFICIENT_EVIDENCE` / `UNVERIFIED`).
4. Every LLM call goes through `AIRunRecorder` (provider, model, prompt id/version/hash).
5. Every state change writes an `AuditService.record(...)` event in the same transaction.
6. No agent approves its own work. Only a human `review_decisions` row makes a claim `APPROVED`.
7. Agent loops are bounded (`BNIP_MAX_REVISION_ROUNDS`, stage `max_attempts`); exhaustion escalates to a human.
8. Never build: voter-level profiling, fake personas or impersonation, deceptive bots,
   astroturfing, or publishing without human approval. See SECURITY.md §5.
9. Mock providers are test infrastructure. Never use them to make the UI look functional.
10. Don't build social publishing before the Milestone 1 pipeline works end to end.

## Stack

- Backend: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 (sync, psycopg 3), Alembic, Celery + Redis. Managed with `uv`.
- DB: PostgreSQL 16 + pgvector (768-dim embeddings).
- AI: `LLMProvider` / `EmbeddingProvider` protocols; Ollama and scripted mock implementations.
- Frontend: Next.js 16 (App Router, `cacheComponents` on), React 19, TypeScript, Tailwind v4, shadcn/ui conventions. React Flow and Recharts get added in Phases 2 and 4.
- **Next.js 16 differs from older versions.** Read `frontend/AGENTS.md` and the docs in `frontend/node_modules/next/dist/docs/` before writing frontend code.

## Commands (run from `bharat-nip/`)

```bash
make infra-up            # docker: postgres+pgvector, redis
make backend-install frontend-install
make migrate             # alembic upgrade head
make dev-api | dev-worker | dev-web
make test-backend        # ruff + pytest (needs Postgres + Redis)
make test-frontend       # eslint + typecheck + vitest
make check               # everything CI runs, incl. next build
```

New migration: `cd backend && uv run alembic revision --autogenerate -m "..."`.
Review it by hand, make sure `downgrade()` works, and confirm `test_migrations.py` passes
(round trip plus no model/migration drift).

## Conventions

- Keep everything inside `bharat-nip/`. The repo root holds unrelated projects (`trader-desk/`, `resume/`, `job-tracker.md`).
- Enum values are defined once in `backend/app/domain/enums.py`, and stored as VARCHAR + CHECK.
- Claim status changes must call `app.domain.state.assert_transition`.
- Business logic lives in `app/services` (session-in, no HTTP, no Celery), so routes and tasks stay thin.
- Prompts live at `app/prompts/<id>/<vN>.md`. Never edit a released version; add a new one.
- DB tests use the real `bnip_test` database (transaction rollback per test). Don't mock SQLAlchemy.
- Add a regression test with every bug fix. Keep the app runnable and `make check` green after every phase.

## Environment variables

Backend: all `BNIP_*`, documented in `backend/.env.example` and ARCHITECTURE.md §8.
Frontend: `BNIP_API_URL` (server-side), in `frontend/.env.example`.
Never commit real secrets.
