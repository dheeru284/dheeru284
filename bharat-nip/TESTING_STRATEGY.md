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
| Pipeline end-to-end | pytest, inline dispatcher, `MockLLMProvider` + `MockSearchProvider` | submission → … → review → audit | ✔ |
| Invariance | pytest | speaker/party swap ⇒ identical blinded text, prompts and verdicts | ✔ |
| Frontend unit | Vitest | API client and formatters | ✔ |
| Frontend build | `next build`, `tsc --noEmit`, ESLint | | ✔ |
| Frontend E2E | Playwright | submit → review flow | manual run in Phase 1 (screenshots), CI in Phase 2 |
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

## 3. Principle-to-test map (implemented)

| Principle | Test(s) in `backend/tests/` |
|---|---|
| **End-to-end pipeline** | `test_pipeline_e2e.py` (service level) and `test_api_e2e.py` (over HTTP): submission → extracted claim → search → evidence → ranking → assessment → critic REVISE → revised assessment → critic PASS → human review → structured result → audit trail and chain verification. MockLLM and MockSearchProvider only; no network, no paid API. |
| Speaker independence | `test_invariance.py`: three fictional speakers from different parties give identical blinded text, assessor input hash and classification; no name or party reaches the assessor. Blinding unit tests. |
| Never force a classification | `test_pipeline_paths.py`: no evidence ⇒ `INSUFFICIENT_EVIDENCE` by rule with zero assessor calls; opinions are not researched. |
| No fabricated evidence | Fabricated quote rejected and audited; every stored quote equals its source slice; quote location matches whitespace differences only, never paraphrase (`test_text_utils.py`). |
| No fabricated sources | Sources come only from search/ingest; content-hash dedupe (`test_api_registry_sources.py`). |
| Bounded loops | Critic always REVISE ⇒ exactly `MAX_REVISION_ROUNDS` + 1 assessments, then `LOOP_LIMIT`. Invalid output retried once with the error appended. |
| Critic independence and enforcement | PASS overridden to ESCALATE (`RULE_FLAG`) when contradicting evidence was ignored. |
| Calibration and ranking | `test_ranking_and_calibration.py`: weights, recency, document quality, scoped/expiring authority, confidence caps. |
| Failure handling | Unscripted assessor ⇒ `STAGE_FAILURE` review task, and the failed `ai_runs` row is kept. |
| Human review | Four-eyes (`403`), notes required, one decision per task (`409`), NEEDS_MORE_RESEARCH → re-run → new revision. |
| Submission types | `test_api_submissions.py`: text, URL (mocked transport), article, PDF (real generated PDF), image → NEEDS_TRANSCRIPTION → transcription, video metadata, byte-sniffed uploads, idempotency, submitter visibility. |
| SSRF | `test_ingest.py`: blocked schemes, credentials, private/loopback/link-local/metadata IPs, private DNS answers, redirects to private addresses, size limit. |
| Source registry | Rationale required, verification sets review date, edits reset verification, all audited. |
| Provenance | Every agent call recorded with provider, model, prompt id/version/sha256; `GET /ai-runs/{id}`. |
| Audit trail | Append-only triggers, tamper detection, required actions present for a full run. |
| Migrations | Round trip, no model drift, and **every enum CHECK matches its Python enum** (`test_enum_constraints.py`). |
| Mock safety | Mocks and fixtures refused in production and without the explicit flag in development; unscripted mock calls raise. |

| **Narrative intelligence** | `test_narrative_units.py` (similarity, velocity, bursts, observation growth, evidence status/strength, interest, coverage and staleness, harm signals, emerging rule, **every rule of the recommendation table**, every recommendation reachable, status transitions), `test_narrative_engine.py` (detection, idempotency, assignment, evidence-driven recommendation changes, contested/escalation, emerging topics, relations, manual operations and exclusions, reactivation, history matching, claim history, timeline, graph, audit), `test_api_narratives.py` (end-to-end over HTTP on top of the real pipeline, membership operations, RBAC). |
| **Narrative neutrality and privacy** | Swapping every claim's speaker and party changes **no** metric snapshot; recommendation inputs are exactly the six required ones; the narrative package never references speaker attribution or persuasion; narrative tables have no person-, account- or politics-shaped columns; observations accept only aggregate fields; graph entity edges exclude speakers. |

| **Agent organization** | `test_org_engine.py`: 14 complete definitions, the hierarchy is a tree, no publish/send/contact tool or permission, no step reviewed by its own agent, every workflow end to end (media check with reuse and limitations, submission fact-check leaving verdicts to humans, claim investigation with a revision, narrative response with human approval, skipped content when no response is recommended, analytics), iteration-limit escalation with bounded retry, task budget, token limit before any LLM call, tool permission denial, invented-number rejection, compliance violation → human revision (limit 2) → reject, the strategist cannot override the engine, unsupported languages, org chart status/performance/activity. `test_api_org.py`: the same over HTTP, including four-eyes approval and RBAC. |

All test data is fictional (`tests/scenario.py`: "Riverland" and its statistics office). The
tests never assert facts about real places, people or statistics.

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
