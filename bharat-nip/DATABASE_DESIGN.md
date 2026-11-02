# Database Design

PostgreSQL 16 with the `vector` extension (pgvector). The schema is managed only by
Alembic (`backend/alembic/versions`):

| Revision | Content |
|---|---|
| `0001` | Phase 0 baseline: users, entities, submissions, claims, sources, chunks, evidence, assessments, critiques, review, ai_runs, pipeline_jobs, audit_events (append-only triggers). |
| `0004` | Phase 3: agent organization (§3.19). New tables only. |
| `0003` | Phase 2: narrative intelligence tables (§3.18). New tables only. |
| `0002` | Phase 1: submission types and files, structured claims, **source registry** (replaces `publishers`), **search queries/results** (replace `retrieval_results`), evidence relevance and directness, structured fact-check results, critic findings, and the new review model. Hand-written, with explicit enum CHECK changes. |

The SQLAlchemy models in `backend/app/models` mirror this document.

## 1. Conventions

- Primary keys: application-generated UUIDv4, except `audit_events.seq` (`BIGINT GENERATED ALWAYS AS IDENTITY`).
- Timestamps: `TIMESTAMPTZ` in UTC. `created_at` on every table; `updated_at` on mutable ones.
- Enumerations: `VARCHAR(n)` plus a named `CHECK` (`ck_<table>_<column>`). Values are defined once in
  `app/domain/enums.py`. Autogenerate cannot see CHECK changes, so `tests/test_enum_constraints.py`
  compares every enum CHECK in the migrated database with its Python enum.
- `JSONB` only where the shape is versioned elsewhere (agent I/O, ranking components, critic checks, audit payloads, entity lists).
- Foreign keys use the default `RESTRICT`. Pipeline data is part of the record and is never cascade-deleted.
- Constraint names follow a fixed convention (`pk_`, `fk_`, `uq_`, `ix_`, `ck_`) set in `app/db/base.py`.

## 2. Relationships

```
users ─< submissions ── stored_files (image/PDF bytes on disk, addressed by sha256)
            │   └── entities (speaker, attribution only)
            └─< claims
                  ├─< search_queries ─< search_results ── sources ── registry_sources
                  ├─< evidence ── sources ─< source_chunks
                  │      └─< evidence_rankings
                  ├─< assessments ─< assessment_citations >── evidence
                  │      ├─< critiques
                  │      └─< review_tasks ── review_decisions (1:1) ── users
                  └─< pipeline_jobs
ai_runs        (referenced by claims, evidence, assessments, critiques; linked to pipeline_jobs)
audit_events   (references any entity by type + id; no FKs)
```

## 3. Tables

### 3.1 `users`
`id`, `email` (unique, lower-cased), `display_name`, `role` (`ADMIN`, `REVIEWER`, `ANALYST`,
`SUBMITTER`), `password_hash` (Argon2id), `is_active`, timestamps.

### 3.2 `entities`
Public speakers and organizations only (never private citizens). `name`, `entity_type`
(`PERSON`, `ORGANIZATION`, `POLITICAL_PARTY`, `GOVERNMENT_BODY`, `MEDIA_OUTLET`, `PLACE`, `OTHER`), `description`.

### 3.3 `stored_files`
Uploaded images and PDFs. `sha256`, `filename`, `content_type` (sniffed from the bytes, not the
client's header), `size_bytes`, `storage_path` (relative to `BNIP_STORAGE_DIR`), `uploaded_by_id`.

### 3.4 `submissions`
| Column | Notes |
|---|---|
| `submission_type` | `TEXT`, `URL`, `ARTICLE`, `IMAGE`, `PDF`, `VIDEO_METADATA` |
| `raw_text` | what the user typed: claim text, article body, caption, or transcription (≤ 20,000) |
| `source_url`, `title`, `publisher_name`, `published_at` | as supplied, or filled from the fetched page |
| `metadata` | JSONB: `video` metadata; `fetch` record for URL submissions (final URL, status, content type, body hash, redirects) |
| `file_id` | → `stored_files` for IMAGE/PDF |
| `speaker_entity_id`, `statement_date`, `language`, `context_note` | |
| `idempotency_key` | unique per submitter |
| `extracted_text` | machine-readable text that claim extraction runs on (≤ 200,000) |
| `extraction_method` | `USER_TEXT`, `HTML_EXTRACTION`, `PDF_TEXT`, `OCR`, `USER_TRANSCRIPTION`, `VIDEO_METADATA` |
| `extraction_notes` | e.g. "OCR is not installed on this server; a human transcription is required" |
| `status` | `RECEIVED`, `PROCESSING`, `PROCESSED`, `NEEDS_TRANSCRIPTION`, `NO_CLAIMS`, `FAILED` |

### 3.5 `claims`
| Column | Notes |
|---|---|
| `id` | claim ID |
| `text` | the claim as stated |
| `normalized_text` | **blinded**: speaker replaced with `[SPEAKER]`. The only text the assessor and critic see. |
| `subject`, `predicate`, `object` | the core triple |
| `time_reference`, `claim_date` | time as stated ("2023"); `claim_date` only if an exact day is stated |
| `location` | |
| `entities` | JSONB `[{name, type, role}]`, role `SPEAKER` / `SUBJECT` / `MENTIONED` |
| `original_source` | JSONB `{submission_id, submission_type, url, title, publisher, published_at, extraction_method}` |
| `claim_type`, `checkworthy`, `language` | type: `FACTUAL`, `OPINION`, `PREDICTION`, `SATIRE`, `UNCLEAR` |
| `speaker_entity_id`, `statement_date` | attribution; never sent to assessment prompts |
| `status` | see §4 |
| `extraction_ai_run_id` / `created_by_id` | CHECK: at least one is set |
| `extracted_at` | |

### 3.6 `registry_sources` (source registry)
Describes what kind of source an origin is and **where** it has authority. It is deliberately
**not** a permanent true/false list of publishers:

- authority is scoped to a `jurisdiction` and to `authority_scope` topics, and drops to `GENERAL` for claims outside that scope;
- it counts only while `verification_status = VERIFIED` and `review_due_at` is in the future, and is treated as `UNASSESSED` otherwise;
- any substantive edit resets verification to `UNVERIFIED`;
- it affects evidence **ranking** only, never a verdict directly;
- political alignment is not a field and is never a criterion.

| Column | Notes |
|---|---|
| `name`, `domain` (unique, normalized, matched against the URL host and parent domains) | |
| `category` | `GOVERNMENT`, `STATISTICAL_AGENCY`, `REGULATOR`, `COURT`, `LEGISLATURE`, `ELECTION_BODY`, `INTERNATIONAL_ORGANIZATION`, `ACADEMIC`, `NEWS_MEDIA`, `FACT_CHECKER`, `NGO`, `CORPORATE`, `POLITICAL_PARTY`, `SOCIAL_MEDIA`, `OTHER` |
| `jurisdiction` | ISO code / subdivision or `GLOBAL` |
| `authority_level` | `PRIMARY_AUTHORITY`, `ESTABLISHED`, `GENERAL`, `LIMITED`, `UNASSESSED` |
| `authority_scope`, `authority_rationale` | CHECK: rationale required unless `UNASSESSED` |
| `default_source_type`, `is_primary_source` | primary vs secondary |
| `verification_status` | `UNVERIFIED`, `VERIFIED`, `DISPUTED` |
| `verification_method`, `verification_notes`, `verified_by_id`, `verified_at`, `review_due_at` | CHECK: VERIFIED requires verifier, time and review date |

### 3.7 `sources` (document snapshots)
Immutable. Created only by human ingest or the search stage. `registry_source_id`, `source_type`
(`OFFICIAL_RECORD`, `STATISTICAL_DATA`, `LEGAL_DOCUMENT`, `ACADEMIC`, `NEWS_REPORT`, `FACT_CHECK`,
`PRESS_RELEASE`, `SOCIAL_MEDIA_POST`, `OTHER`), `is_primary`, `title`, `url`, `publisher_name`,
`published_at`, `retrieved_at`, `retrieval_provider`, `language`, `content_text`,
`content_sha256` (unique), `fetch_metadata` (final URL, status code, content type, redirects),
`ingested_by_id`.

### 3.8 `source_chunks`
Paragraph-based chunks with exact offsets (`text == content_text[char_start:char_end]`),
`text_search` (generated tsvector, GIN index) and `embedding vector(768)` (HNSW index; populated
from Phase 2).

### 3.9 `search_queries` and `search_results`
One `search_queries` row per (provider, query) per claim: `provider`, `query_text`, `status`,
`result_count`, `error`, `executed_at`, `pipeline_job_id`. Each hit is a `search_results` row
with `rank`, `url`, `title`, `snippet`, `provider_score`, `source_id` (when snapshotted), and
`fetch_status` (`FETCHED`, `PROVIDED`, `REUSED`, `FAILED`, `SKIPPED`) plus `fetch_error`. This
is how a missing piece of evidence can be diagnosed.

### 3.10 `evidence`
| Column | Notes |
|---|---|
| `claim_id`, `source_id`, `chunk_id` | |
| `quote`, `quote_char_start`, `quote_char_end` | the **stored** slice of the source, located mechanically; never the model's copy |
| `stance` | support/contradiction relationship: `SUPPORTS`, `REFUTES`, `MIXED`, `CONTEXT` (`NOT_RELEVANT` proposals are not stored) |
| `stance_rationale`, `directness` (`DIRECT`/`INDIRECT`) | |
| `relevance` = mean(`lexical_relevance`, `agent_relevance`) | CHECK 0..1 |
| `extracted_by_ai_run_id` / `created_by_id` | CHECK: exactly one |

### 3.11 `evidence_rankings`
`evidence_id`, `ranking_version` (`rank-v2`), `score` (0..1), `components` (every factor, weight,
authority basis, recency basis, quality signals, origin). Unique per (evidence, version), and
updated in place when re-ranked after more research.

### 3.12 `assessments`
One row per revision. `revision`, `parent_assessment_id`, `classification` (the 10 values),
`confidence` (0..1, after calibration caps), `confidence_raw` (what the agent proposed), `summary`,
`reasoning`, `missing_information` (JSONB list), `recommended_action` (`CONFIRM_IN_REVIEW`,
`ADD_CONTEXT_NOTE`, `SEEK_PRIMARY_SOURCE`, `GATHER_MORE_EVIDENCE`, `CONSULT_SUBJECT_EXPERT`,
`NOT_FACT_CHECKABLE`), `guardrails` (JSONB list of rules that fired), `produced_by`
(`AGENT`/`RULE`; CHECK ties `RULE` ⇔ no `ai_run_id`), `status` (`DRAFT`, `CRITIQUED`,
`SUPERSEDED`, `PENDING_REVIEW`, `APPROVED`, `REJECTED`, `NEEDS_MORE_RESEARCH`).

`assessment_citations(assessment_id, evidence_id)` lists the evidence the assessment relied on.

### 3.13 `critiques`
`assessment_id`, `outcome` (final), `agent_outcome` (what the critic said), `outcome_overridden`,
`checks` (JSONB: the 8 checks with pass/fail, detail, evidence IDs), `deterministic_findings`
(JSONB with severity), `counter_argument`, `suggested_classification`, `summary`, `ai_run_id`.

### 3.14 `review_tasks` and `review_decisions`
`review_tasks`: `claim_id`, `assessment_id` (nullable for stage failures), `reason` (`ROUTINE`,
`CRITIC_ESCALATION`, `RULE_FLAG`, `LOOP_LIMIT`, `LOW_CONFIDENCE`, `INSUFFICIENT_EVIDENCE`,
`STAGE_FAILURE`), `reason_detail`, `priority`, `status` (`OPEN`, `DECIDED`, `CANCELLED`).

`review_decisions` (one per task): `reviewer_id` (≠ submitter, enforced by the service),
`decision` (`APPROVE`, `REJECT`, `NEEDS_MORE_RESEARCH`), `final_classification` (CHECK: required
for APPROVE), `notes` (CHECK: required for REJECT and NEEDS_MORE_RESEARCH; the service also
requires notes when APPROVE changes the classification).

### 3.15 `ai_runs`
One row per LLM call attempt (succeeded, failed or invalid): `agent_name`, `agent_version`,
`provider`, `model`, `prompt_id`, `prompt_version`, `prompt_sha256`, `input_sha256`,
`input_messages`, `parameters`, `output_text`, `output_parsed`, `status`, `error`, token counts,
`latency_ms`, `attempt`, `pipeline_job_id`.

### 3.16 `pipeline_jobs`
One row per stage execution: `stage` (`CONTENT`, `EXTRACTION`, `SEARCH`, `EVIDENCE`, `RANKING`,
`ASSESSMENT`, `CRITIQUE`, `REVIEW_ROUTING`), `status`, `attempt`/`max_attempts` (CHECK bounded),
`error`, timings.

### 3.17 `audit_events`
Append-only, hash-chained. `seq`, `id`, `occurred_at`, `actor_type` (`USER`, `AGENT`, `SYSTEM`),
`actor_id`, `action`, `entity_type`, `entity_id`, `payload`, `prev_hash`,
`hash = sha256(prev_hash ‖ canonical_json(fields))`. Triggers block UPDATE, DELETE and TRUNCATE;
appends take a transaction-scoped advisory lock so the chain stays linear.

Actions recorded in Phase 1: `user.created`, `user.updated`, `entity.created`, `submission.created`,
`submission.content_extracted`, `submission.needs_transcription`, `submission.transcription_added`,
`submission.failed`, `claim.extracted`, `claim.rejected`, `claim.status_changed`, `search.executed`,
`source.created`, `evidence.created`, `evidence.rejected`, `evidence.ranked`, `ai_run.recorded`,
`assessment.created`, `assessment.revised`, `critique.created`, `review_task.created`,
`review.decided`, `registry.created`, `registry.updated`, `registry.verification_set`.

### 3.18 Narrative intelligence (Phase 2)
Full semantics are in [NARRATIVE_INTELLIGENCE.md](NARRATIVE_INTELLIGENCE.md). None of these tables
holds data about individual members of the public. `tests/test_narrative_engine.py` fails if a
person-, account- or politics-shaped column is added.

| Table | Purpose and key columns |
|---|---|
| `topics` | Coarse claim clusters: `label`, `keywords`, `claim_count`, `recent_count`, `baseline_weekly`, `is_emerging`, `emerging_since`. |
| `topic_claims` | Derived claim → topic map (PK `claim_id`), rebuilt by every engine run. |
| `narratives` | `title` (speaker-free), `summary`, `status` (`EMERGING`, `MONITOR`, `INVESTIGATE`, `RESPOND`, `CORRECT`, `RESOLVED`, `ARCHIVED`), `origin` (`DETECTED`/`MANUAL`), `topic_id`, `first_seen_at`, `last_seen_at`, analyst harm assessment (`harm_category`, `harm_severity`, `harm_rationale` — CHECK: rationale required for LOW+), status note/actor/time. |
| `narrative_claims` | Membership (unique per claim): `similarity`, `added_by` (`ENGINE`/`USER`), `excluded` (an analyst removed it; the engine never re-adds it). |
| `narrative_relations` | Derived undirected edges (`source_id < target_id` CHECK): `relation_type` (`SIMILAR`, `SAME_TOPIC`, `SHARES_ENTITY`, `SHARES_EVIDENCE`, `CONTRADICTS`), `weight`, `details`. |
| `narrative_metrics` | Snapshots, written only when something changed: `version` (monotonic per narrative), `computed_at`, `engine_version`, claim count, `rate_7d`, `acceleration`, `recurring`, `evidence_status`, `evidence_strength`, `public_interest`, `momentum`, `harm_score`, `uncertainty`, `coverage` (CHECK 0..1), `recommendation`, `suggested_status`, `details` (indicators, harm signals, rule trace). |
| `narrative_observations` | Aggregate public counts: `observed_at`, `channel`, `metric` (`MENTIONS`, `SHARES`, `VIEWS`, `ARTICLES`, `SEARCH_INTEREST`), `value` ≥ 0, `source_url`. No person, account or handle fields. |
| `narrative_responses` | Existing response coverage: `response_type` (`FACT_CHECK`, `CORRECTION`, `CLARIFICATION`, `CONTEXT_NOTE`, `EXTERNAL_FACT_CHECK`), `title`, `url`, `channel`, `published_at`. |

Narrative audit actions: `narrative.created`, `narrative.claim_added`, `narrative.claim_removed`,
`narrative.status_changed`, `narrative.harm_assessed`, `narrative.updated`,
`narrative.observation_added`, `narrative.response_recorded`, `narrative.recommendation_changed`,
`topic.created`, `narrative_engine.run`.

### 3.19 Agent organization (Phase 3)
Agent definitions are code (`app/org/agents.py`); see [AGENT_ORGANIZATION.md](AGENT_ORGANIZATION.md).

| Table | Purpose and key columns |
|---|---|
| `org_tasks` | `workflow`, `title`, `input`, `status` (`PENDING`, `IN_PROGRESS`, `AWAITING_APPROVAL`, `ESCALATED`, `COMPLETED`, `REJECTED`, `FAILED`, `CANCELLED`), `approval_level` (`MANAGER`/`HUMAN`), `output` (delegation plan and result), `escalation_reason`, `executions_used`, `human_revisions`, `created_by_id`. |
| `org_task_steps` | One per template step (unique `task_id, step_key`): `agent_key`, `delegated_by`, `depends_on`, `reviewer` (`CRITIC`/`MANAGER`/`NONE`), `status`, `iterations`, `retries`, `output`, `feedback`, `escalation`. |
| `org_executions` | The execution log, ordered by `seq` (identity): `kind` (`DELEGATION`, `EXECUTION`, `REVIEW`, `REVISION`, `ESCALATION`, `APPROVAL`, `COMPLETION`), `status`, `agent_key` (`human_reviewer` for human decisions), `iteration`, `input`, `output`, `tool_calls`, `ai_run_id`, `model`, token counts, `latency_ms`, `error`. |
| `org_approvals` | `approver_type` (`HUMAN`/`AGENT`; CHECK identity present), `decision` (`APPROVED`, `REJECTED`, `REVISION_REQUESTED`; CHECK notes required unless approved), `target_step`. |

Every execution is also an `org.<kind>` audit event; task lifecycle events are `org.task_created`,
`org.task_retried` and `org.task_cancelled`.

## 4. Claim status machine (`app/domain/state.py`)

| From | Allowed next | Notes |
|---|---|---|
| `EXTRACTED` | `RESEARCHING`, `ASSESSING`, `FAILED` | `ASSESSING` directly for OPINION / PREDICTION / SATIRE |
| `RESEARCHING` | `ASSESSING`, `FAILED` | search, evidence, ranking |
| `ASSESSING` | `CRITIQUING`, `PENDING_REVIEW`, `FAILED` | rule-produced assessments skip the critic |
| `CRITIQUING` | `ASSESSING`, `PENDING_REVIEW`, `FAILED` | `ASSESSING` = the bounded REVISE loop |
| `PENDING_REVIEW` | `APPROVED`, `REJECTED`, `NEEDS_MORE_RESEARCH` | human decisions only |
| `NEEDS_MORE_RESEARCH` | `RESEARCHING` | analyst re-runs research |
| `FAILED` | `PENDING_REVIEW` | stage failures always reach a human |
| `APPROVED`, `REJECTED` | — | terminal |

The human-review view (`ReviewStatus`) is derived from this: `PENDING_REVIEW`, `APPROVED`,
`REJECTED`, `NEEDS_MORE_RESEARCH`, and `NOT_READY` for everything else.

## 5. Data retention and privacy

- No table stores data about private individuals beyond platform users.
- Sources are public documents. Rows are never hard-deleted; retraction is a status change plus an audit event.

## 6. Migration policy

- One revision per logical change; autogenerate, then hand-review. Enum value changes need explicit CHECK edits.
- Every migration has a working `downgrade()`. `0002` refuses to run in either direction if the reshaped tables contain rows.
- CI runs `upgrade head → downgrade base → upgrade head`, then checks for model/migration drift and enum/CHECK consistency.
