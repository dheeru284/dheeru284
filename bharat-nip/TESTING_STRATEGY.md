# Testing Strategy

The test suite is how we prove the platform's promises. A principle that
isn't tested isn't enforced.

## 1. Test layers

| Layer | Tooling | Scope | Runs in CI |
|---|---|---|---|
| Unit | pytest | enums, state transitions, ranking math, quote verification, prompt hashing, blinding, config guards | ✔ |
| Integration (DB) | pytest + real PostgreSQL (`bnip_test`) | models, constraints, services, audit trigger and chain | ✔ |
| Migration | pytest + Alembic | `upgrade head`, `downgrade base`, `upgrade head` on an empty DB; models match migrations (no autogenerate diff) | ✔ |
| API | pytest + FastAPI `TestClient` | routes, auth/RBAC, problem+json errors | ✔ |
| Provider contract | pytest | each provider passes the same contract tests; Ollama via an HTTP mock transport (`httpx.MockTransport`), plus an opt-in live test | ✔ (live: manual) |
| Pipeline end-to-end | pytest, Celery eager mode, `MockLLMProvider` with scripted responses | submission → … → review → audit | ✔ (Phase 1) |
| Invariance | pytest | speaker/party swap ⇒ identical blinded text, prompts and verdicts | ✔ (Phase 1) |
| Frontend unit | Vitest | API client and formatters | ✔ |
| Frontend build | `next build`, `tsc --noEmit`, ESLint | | ✔ |
| Frontend E2E | Playwright (pre-installed Chromium) | submit → review flow | ✔ (Phase 2) |
| Model evaluation | `backend/evals/` scripts | golden set vs real providers | manual / scheduled |

## 2. Rules

1. **Real database for DB tests.** We do not mock SQLAlchemy. Tests use
   PostgreSQL with pgvector, because CHECK constraints, triggers and vector
   types are part of the behaviour.
2. **Isolation:** each test runs in a transaction that is rolled back (SAVEPOINT pattern).
   Migration tests use a dedicated scratch database created per run.
3. **Mocks only at the provider boundary.** The `MockLLMProvider` is the only
   LLM stand-in. Tests script exactly the responses they need.
4. **No network in CI** except to local services (Postgres, Redis).
5. **Every bug fix adds a regression test.**
6. **Determinism:** fixed seeds, frozen time where timestamps matter, `temperature=0`.

## 3. Principle-to-test map

| Principle | Test(s) |
|---|---|
| No fabricated evidence | Evidence service rejects non-substring quotes; DB-wide check that every `evidence.quote` equals the source slice. |
| No fabricated sources | No code path outside retrieval/ingest services inserts `sources` (enforced by review); ingest test checks hash and immutability. |
| Insufficient evidence | Claim with zero evidence ⇒ `INSUFFICIENT_EVIDENCE`, `produced_by=RULE`, no LLM call (mock records zero calls). |
| Provenance | Every agent call creates an `ai_runs` row with provider, model, prompt_id, version and sha256 (Phase 0: `AIRunRecorder` test). |
| No self-approval | Critic with the same `agent_name` as assessor is refused; reviewer = submitter gets `403`; no service sets `APPROVED` without a decision. |
| Bounded loops | Critic scripted to always `REVISE` ⇒ exactly `MAX_REVISION_ROUNDS` revisions, then a `LOOP_LIMIT` review task. |
| Speaker independence | Invariance suite: N claims × M speakers from different parties ⇒ identical assessor input hash and verdict. |
| Audit trail | UPDATE/DELETE/TRUNCATE on `audit_events` raise; chain verification detects tampering (tested by bypassing the trigger as superuser in a scratch DB); every service mutation emits its event. |
| Mock safety | Settings refuse mock providers in production, and in development without the explicit flag. Unscripted mock calls raise. |
| Reproducible migrations | Migration round-trip test plus a "no pending autogenerate diff" test. |

## 4. Running tests

```bash
make test-backend      # ruff + pytest (needs Postgres + Redis running)
make test-frontend     # lint + typecheck + vitest
make build-frontend
```

`BNIP_TEST_DATABASE_URL` points at the test DB (default
`postgresql+psycopg://bnip:bnip@localhost:5432/bnip_test`).

## 5. CI

`.github/workflows/bnip-ci.yml` (repo root) runs on changes under `bharat-nip/**`:
- backend job: `pgvector/pgvector:pg16` and `redis:7` services, `uv sync`, ruff, pytest;
- frontend job: `npm ci`, lint, typecheck, vitest, build.

## 6. Phase exit criteria

A phase is done only when: all CI jobs are green, migrations round-trip, the
docs reflect what was built, and `make infra-up migrate dev-api dev-worker dev-web` brings up a working stack.
