# API Design

REST + JSON. Base path `/api/v1`. OpenAPI at `/api/v1/openapi.json`, interactive docs at
`/api/v1/docs`. Every endpoint below is implemented and covered by tests (Phase 1).

## 1. Conventions

- **Auth:** `Authorization: Bearer <JWT>` from `POST /auth/token`. Roles are ordered
  SUBMITTER < ANALYST < REVIEWER < ADMIN; "ANALYST+" means analyst or higher.
- **Object access:** submitters see only their own submissions and claims, and see evidence and
  results only after a reviewer has **approved** the claim. Analysts and above see everything.
- **IDs** are UUID strings. **Timestamps** are ISO 8601 UTC. **Enums** are upper-snake strings from `app/domain/enums.py`.
- **Pagination** (list endpoints that return `Page`): `?limit=50&cursor=<opaque>` returns
  `{"items": [...], "next_cursor": "..."|null}`.
- **Idempotency:** `POST /submissions` and `/submissions/upload` accept `Idempotency-Key`. A
  repeat from the same user returns the original with `200`.
- **Errors:** RFC 9457 `application/problem+json` (`type`, `title`, `status`, `detail`,
  `instance`; validation adds `errors`). Domain errors map to 403/404/409/422.
- **Provenance:** results carry `provenance {ai_run_id, agent_name, provider, model, prompt_id,
  prompt_version, prompt_sha256, is_mock}`.

## 2. Endpoints

### System
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | — | Liveness |
| GET | `/health/ready` | — | DB, pgvector, Redis, LLM and embedding providers; `503` if a required check fails (AI is required only in production) |
| GET | `/system/providers` | — | Configured LLM and embedding providers, with `is_mock` |

### Auth and users
| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/auth/token` | — | `{email, password}` → `{access_token, token_type, expires_in}` |
| GET | `/auth/me` | any | Current user |
| GET / POST | `/users` | ADMIN | List / create users (audited) |
| PATCH | `/users/{id}` | ADMIN | Change role or active flag (audited) |

The first admin is created with `uv run python -m app.cli create-user --role ADMIN ...`.

### Submissions
| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/submissions` | any | JSON submission of type `TEXT`, `URL`, `ARTICLE` or `VIDEO_METADATA`; starts the pipeline. `201` `{submission, created}` |
| POST | `/submissions/upload` | any | Multipart: `file` (PNG/JPEG/GIF/WEBP/PDF, type sniffed from bytes, ≤ 15 MB) + `payload` (the same JSON, type `IMAGE` or `PDF`) |
| GET | `/submissions` | any | Own submissions (ANALYST+: all; `?mine=true` to filter) |
| GET | `/submissions/{id}` | owner / ANALYST+ | Submission, its claims, CONTENT/EXTRACTION jobs |
| POST | `/submissions/{id}/transcription` | owner / ANALYST+ | `{text}` for a `NEEDS_TRANSCRIPTION` submission; restarts the pipeline |

Submission body (`SubmissionInput`):
```json
{"submission_type": "TEXT|URL|ARTICLE|IMAGE|PDF|VIDEO_METADATA",
 "raw_text": "...", "source_url": "https://...", "title": "...", "publisher_name": "...",
 "published_at": "...", "language": "en", "context_note": "...",
 "speaker_entity_id": "...", "statement_date": "2024-03-02",
 "video": {"platform": "...", "video_url": "...", "title": "...", "description": "...",
           "uploader": "...", "published_at": "...", "duration_seconds": 0, "transcript": "..."}}
```
Video is never downloaded: metadata plus a submitter-supplied transcript only.

### Claims and results
| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/claims` | any (scoped) | Filters: `status`, `review_status`, `claim_type`, `submission_id` |
| GET | `/claims/{id}` | owner / ANALYST+ | Claim (subject/predicate/object, time, location, entities, original source, extracted_at), pipeline jobs, open review task |
| GET | `/claims/{id}/fact-check` | ANALYST+, or owner after approval | **The structured fact-check result** (§3) |
| GET | `/claims/{id}/evidence` | ANALYST+, or owner after approval | Ranked evidence with URL, title, publisher, dates, source type, relevance, stance, content hash and rank components |
| GET | `/claims/{id}/assessments` | ANALYST+, or owner after approval | Every revision with citations and critiques |
| GET | `/claims/{id}/searches` | ANALYST+ | Every search query and its results and fetch outcomes |
| GET | `/claims/{id}/audit` | ANALYST+ | Audit events for the claim, its submission, assessments, review tasks and agent runs |
| POST | `/claims/{id}/research` | ANALYST+ | Re-run research and assessment for a `NEEDS_MORE_RESEARCH` claim. `202` |

### Source registry, sources, entities
| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/registry` | ANALYST+ | Registry entries |
| POST | `/registry` | ADMIN | Create; `authority_rationale` required unless `UNASSESSED` |
| PATCH | `/registry/{id}` | ADMIN | Edit; a substantive edit resets verification to `UNVERIFIED` |
| POST | `/registry/{id}/verification` | ADMIN | `{status, method, notes, review_period_days}`; sets `review_due_at` |
| POST | `/sources` | ANALYST+ | Ingest a document into the local corpus (hashed, chunked, registry-matched). Duplicate content returns `200` with the existing source |
| GET | `/sources`, `/sources/{id}` | ANALYST+ | List / full snapshot |
| GET / POST | `/entities` | ANALYST+ | Public speakers and organizations |

### Review
| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/review-tasks` | REVIEWER+ | Queue (`status`, `reason`), sorted by priority then age; shows `submitted_by_me` |
| GET | `/review-tasks/{id}` | REVIEWER+ | One task |
| POST | `/review-tasks/{id}/decision` | REVIEWER+ | `{decision: APPROVE|REJECT|NEEDS_MORE_RESEARCH, final_classification?, notes?}`. `403` for your own submission (four-eyes), `409` if already decided, `422` for missing notes |

### Audit and provenance
| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/audit-events` | ADMIN | Filters `entity_type`, `entity_id`, `action`, `actor_id`, `after_seq` |
| GET | `/audit-events/verify` | ADMIN | Recompute the hash chain: `{ok, checked, first_broken_seq}` |
| GET | `/ai-runs/{id}` | ANALYST+ | Full agent run: messages, parameters, output, hashes |

### Narrative intelligence (Phase 2; ANALYST+)
| Method | Path | Description |
|---|---|---|
| GET | `/narratives` | Dashboard: narratives with latest metrics, sorted by recommendation priority then momentum; counts by status and recommendation; emerging topics. Filters `status`, `recommendation`, `topic_id`, `include_archived` |
| GET | `/narratives/{id}` | Detail: metrics with rule trace, harm assessment, allowed status transitions, related narratives, observations, responses |
| GET | `/narratives/{id}/claims` | Claim history: member claims in time order with burst numbers, origins and approved classifications (no speakers) |
| GET | `/narratives/{id}/evidence-timeline` | Evidence by publication date (deduplicated per quote, listing supported claims) plus review decisions |
| GET | `/narratives/{id}/metrics` | Metric snapshot history (for charts) |
| GET | `/narratives/graph` | Nodes and edges of the relationship graph (`?topic_id=`) |
| GET | `/topics` | Topics with emerging flags |
| GET | `/claims/{id}/history` | Historical claim matching: earlier similar claims and their approved classifications |
| POST | `/narratives/analyze` | Run the engine now (`202`) |
| POST | `/narratives` | Create a narrative from claim IDs (`409` if a claim already belongs to one) |
| PATCH | `/narratives/{id}` | Title / summary |
| POST | `/narratives/{id}/status` | `{status, note}`; human-only transition table, `409` otherwise |
| PUT | `/narratives/{id}/harm` | `{category, severity, rationale}`; rationale required for LOW+ |
| POST | `/narratives/{id}/claims` | Add a claim (or move one an analyst excluded elsewhere) |
| POST | `/narratives/{id}/claims/{claim_id}/remove` | `{note}`; excludes the claim permanently from engine re-assignment |
| POST | `/narratives/{id}/observations` | Aggregate public count `{observed_at, channel, metric, value, source_url, note}` |
| POST | `/narratives/{id}/responses` | Existing response `{response_type, title, url, channel, published_at}` |

## 3. Structured fact-check result

`GET /claims/{id}/fact-check`:
```json
{
  "classification": "MOSTLY_TRUE",
  "confidence": 0.85,
  "summary": "...",
  "reasoning": "...",
  "supporting_evidence": [ EvidenceItem ],
  "contradicting_evidence": [ EvidenceItem ],
  "missing_information": ["..."],
  "recommended_action": "CONFIRM_IN_REVIEW",

  "context_evidence": [ EvidenceItem ],
  "claim_id": "...", "assessment_id": "...", "revision": 1, "produced_by": "AGENT",
  "confidence_raw": 0.85, "guardrails": [{"rule": "...", "detail": "..."}],
  "assessment_status": "PENDING_REVIEW", "review_status": "PENDING_REVIEW",
  "final_classification": null, "review_decision": null,
  "critic": {"outcome": "PASS", "agent_outcome": "PASS", "outcome_overridden": false,
             "counter_argument": "...", "suggested_classification": null,
             "checks": [...], "deterministic_findings": [...], "provenance": {...}},
  "provenance": {...}
}
```
`EvidenceItem` = `{evidence_id, quote, stance, directness, relevance, rank_score,
ranking_version, cited, source: {source_id, url, title, publisher, published_at, retrieved_at,
source_type, is_primary, authority_level, content_sha256}}`.

Supporting and contradicting lists contain **all** evidence of that stance, ranked, with `cited`
marking what the assessor relied on, so cherry-picking is visible. Confidence is 0 for rule-based
non-determinations (`INSUFFICIENT_EVIDENCE` by rule, OPINION, PREDICTION, SATIRE).

## 4. Async work

Submission and re-research endpoints start the pipeline on a Celery worker
(`BNIP_PIPELINE_EXECUTION=celery`, the default) or inline (`inline`; used by tests). Clients poll
`GET /submissions/{id}` and `GET /claims/{id}`; the web UI refreshes automatically while stages are running.

## 5. Versioning

Breaking changes need `/api/v2`. Additive changes (fields, endpoints, enum values) are allowed in
v1, and clients must tolerate unknown fields and enum values.
