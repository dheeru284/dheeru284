# Bharat Narrative Intelligence Platform (BNIP)

An evidence-first platform for political information, fact-checking, narrative
intelligence and legitimate public communications.

**Core rule:** claims are assessed on evidence alone, never on who made them.
The system can conclude `TRUE`, `MOSTLY_TRUE`, `MISLEADING`, `OUT_OF_CONTEXT`,
`FALSE`, `UNVERIFIED`, `INSUFFICIENT_EVIDENCE`, `OPINION`, `PREDICTION` or
`SATIRE`. It says so explicitly when evidence is insufficient.

**Status: Phase 2 (narrative intelligence) complete.** On top of the Phase 1 evidence pipeline,
the narrative engine groups recurring claims into narratives, tracks topics, velocity, evidence
strength and aggregate public interest, maps relationships, and recommends a response posture for
human decision ([NARRATIVE_INTELLIGENCE.md](NARRATIVE_INTELLIGENCE.md)).

Phase 1: Submit text, URLs, articles, images, PDFs or
video metadata. The system extracts structured claims, searches for evidence, ranks it, proposes
a classification, has an independent critic try to disprove it, and sends every claim to a human
reviewer. Every step is audited. Social-media publishing is deliberately not built (see
[ROADMAP.md](ROADMAP.md)).

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
| [NARRATIVE_INTELLIGENCE.md](NARRATIVE_INTELLIGENCE.md) | Narrative engine: definitions, formulas, recommendation table, neutrality constraints |
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
make dev-beat     # optional: periodic narrative engine runs

make check        # everything CI runs
```

Create the first admin:
```bash
cd backend && uv run python -m app.cli create-user --email you@example.org --name "You" --role ADMIN
```

### Try it without a language model (fictional demo, mock providers)

```bash
cd backend
export BNIP_ALLOW_MOCK_PROVIDERS=true BNIP_LLM_PROVIDER=mock BNIP_EMBEDDING_PROVIDER=mock \
       BNIP_SEARCH_PROVIDERS='["local_corpus"]' \
       BNIP_MOCK_FIXTURES_PATH=$PWD/fixtures/demo_mock.json BNIP_DEMO_PASSWORD=choose-a-password
uv run python -m app.cli seed-demo   # fictional users, registry entry and source
# then run dev-api / dev-worker (same env) and dev-web; sign in as analyst@demo.example
```
Then submit, for example: *At a rally on 2 March 2024, Minister Asha Verma said: "Riverland's
literacy rate rose to 81 percent in 2023." She added that the government was proud of its
schools.* (Riverland and its statistics are fictional.) Search runs for real over the local corpus;
the agents' answers are scripted, recorded with provider `mock`, and shown with a **MOCK** badge.

### Real models and web search
- LLM: `BNIP_LLM_PROVIDER=ollama` with `make ollama-pull` (llama3.1:8b, nomic-embed-text).
  `BNIP_OLLAMA_CRITIC_MODEL` can give the critic a different model.
- Web search: run a [SearXNG](https://docs.searxng.org) instance with JSON output enabled and set
  `BNIP_SEARCH_PROVIDERS='["local_corpus","searxng"]' BNIP_SEARXNG_URL=http://localhost:8888`.
- Local corpus: analysts add documents with `POST /api/v1/sources`.

For real AI output: `make ollama-up && make ollama-pull` (or a host-installed
Ollama). Without Ollama the API still runs, and `/api/v1/health/ready` reports the
AI providers as failing (`degraded`, HTTP 200 in development).

**Without Docker:** the database role needs permission to `CREATE EXTENSION vector`,
because pgvector isn't a trusted extension. Either create the extension as a
superuser in both `bnip` and `bnip_test`, or give the local dev role superuser.
