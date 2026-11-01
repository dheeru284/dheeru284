# Bharat Narrative Intelligence Platform (BNIP)

An evidence-first platform for political information, fact-checking, narrative
intelligence and legitimate public communications.

**Core rule:** claims are assessed on evidence alone, never on who made them.
The system can conclude `TRUE`, `MOSTLY_TRUE`, `MISLEADING`, `OUT_OF_CONTEXT`,
`FALSE`, `UNVERIFIED`, `INSUFFICIENT_EVIDENCE`, `OPINION`, `PREDICTION` or
`SATIRE`. It says so explicitly when evidence is insufficient.

**Status: Phase 0 (foundation).** The design is complete. There is a runnable
backend and frontend skeleton, the full Milestone 1 database schema, provider
abstractions, prompt versioning, AI-run provenance and a hash-chained audit log.
The claim pipeline itself is Phase 1. See [ROADMAP.md](ROADMAP.md).

## Design documents

| Document | What it covers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, data flow, layout, key decisions, config |
| [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) | Rules, roles, verdict definitions, Milestone 1 requirements |
| [DATABASE_DESIGN.md](DATABASE_DESIGN.md) | Every table, constraint and the claim state machine |
| [AI_AGENT_ARCHITECTURE.md](AI_AGENT_ARCHITECTURE.md) | Agents, attribution blinding, prompts, providers, guardrails, loop bounds |
| [API_DESIGN.md](API_DESIGN.md) | REST conventions and the Milestone 1 endpoint contract |
| [TESTING_STRATEGY.md](TESTING_STRATEGY.md) | Test layers and the principle-to-test map |
| [SECURITY.md](SECURITY.md) | Threat model, AI controls, audit integrity, prohibited capabilities |
| [ROADMAP.md](ROADMAP.md) | Phases and exit criteria |

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/), Node 20+, Docker (or a local
PostgreSQL 16 with pgvector, plus Redis 7), and optionally [Ollama](https://ollama.com).

```bash
cd bharat-nip
make infra-up                      # Postgres+pgvector and Redis
make backend-install frontend-install
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
make migrate

make dev-api      # terminal 1: http://localhost:8000/api/v1/docs
make dev-worker   # terminal 2: Celery worker
make dev-web      # terminal 3: http://localhost:3000

make check        # everything CI runs
```

For real AI output: `make ollama-up && make ollama-pull` (or a host-installed
Ollama). Without Ollama the API still runs, and `/api/v1/health/ready` reports the
AI providers as failing (`degraded`, HTTP 200 in development).

**Without Docker:** the database role needs permission to `CREATE EXTENSION vector`,
because pgvector isn't a trusted extension. Either create the extension as a
superuser in both `bnip` and `bnip_test`, or give the local dev role superuser.
