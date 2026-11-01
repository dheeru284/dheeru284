# Narrative Intelligence Engine (Phase 2)

The narrative engine sits **on top of the verified evidence layer** (Phase 1). It groups claims
into narratives, measures how they move, and recommends a response posture. It never decides a
claim's truth itself: truth comes only from human-approved fact-checks.

Engine version: `narr-v1` (`backend/app/narratives/`). Every number below is a constant in
`app/narratives/config.py`; changing one requires a new engine version.

## 1. Non-negotiable constraints

| Constraint | How it is enforced |
|---|---|
| No inference of individual political preference | The engine reads only claims, their public origins, approved fact-checks, evidence, and aggregate counts. There are no tables or fields about members of the public, and nothing is keyed to a person other than platform users and public speakers. |
| No voter psychological profiles | No per-person data exists to profile. Observations are aggregate counts per channel (`narrative_observations` has no person, account or handle field). |
| Aggregate / public information only | Inputs: claim text, submission origins (public URLs/publishers), approved fact-checks, public evidence, analyst-recorded aggregate counts. |
| No political persuasion scores | No metric estimates persuasiveness, audience susceptibility or political effect. Recommendations depend only on the six inputs in §8. |
| Speaker/party neutrality | Similarity uses the **blinded** claim text. Speaker identity is never an input to clustering, metrics or recommendations, and entity relations exclude SPEAKER-role entities. Test: `test_narrative_neutrality.py`. |
| Humans decide | The engine suggests a status and a recommendation. Only analysts change a narrative's status or harm assessment, always with a note, and always audited. RESPOND/CORRECT mean "a human should prepare a response". No content is generated or published in Phase 2. |

## 2. Concepts

| Concept | Definition |
|---|---|
| **Claim occurrence** | A claim with a time `seen_at = coalesce(submission.published_at, statement_date, submission.created_at)`. |
| **Narrative** | A cluster of ≥ 2 similar claims from ≥ 2 different submissions: the same assertion recurring in public. Analysts can also create one manually. |
| **Topic** | A coarser cluster of claims on the same subject. Narratives belong to the topic that holds most of their claims. |
| **Observation** | An analyst- or feed-recorded aggregate public count (mentions, shares, views, articles, search interest) for a narrative on a channel at a time, with a source URL. |
| **Response** | A record that a response already exists: our fact-check, correction, clarification or context note, or an external fact-check. |

## 3. Similarity (`similarity.py`)

- Text for each claim: `normalized_text` (blinded) + `subject` + `object`. Placeholders such as `[SPEAKER]` are removed.
- Terms: `app.domain.text.terms` (lower-case words, numbers kept, stop-words removed).
- TF-IDF with smoothed IDF `ln((1+N)/(1+df)) + 1` over all claims; numeric terms ×2; L2-normalised.
- Cosine similarity. Narrative centroids are normalised sums of member vectors.

Thresholds: `NARRATIVE_SIMILARITY = 0.45`, `TOPIC_SIMILARITY = 0.20`,
`RELATION_SIMILARITY = 0.20`, `HISTORY_MATCH_SIMILARITY = 0.40`.

The `SimilarityBackend` interface allows an embedding backend later. Phase 2 ships only the
lexical backend, because the mock embedding provider has no semantic meaning.

## 4. Detection and clustering (`engine.py`)

The engine is run with a transaction-scoped advisory lock (`run_engine(session, now)`):

1. **Assign** unassigned claims, oldest first, to the most similar existing narrative if
   cosine ≥ `NARRATIVE_SIMILARITY`.
2. **Detect** new narratives: greedily cluster the remaining unassigned claims (same threshold,
   centroid linkage, deterministic order). A cluster with ≥ 2 claims from ≥ 2 submissions becomes a
   narrative (status `EMERGING`, origin `DETECTED`, titled with its most central claim). Singletons
   wait for the next run.
3. **Topics:** greedy clustering of all claims at `TOPIC_SIMILARITY`. Topic IDs are kept stable by
   matching new clusters to existing topics by Jaccard overlap of their claim sets (≥ 0.5). Labels
   are the top 3 terms. Each narrative takes its majority topic.
4. **Relations** (recomputed): see §9.
5. **Metrics and recommendation** for each narrative (§5–§8). A new `narrative_metrics` snapshot is
   written only when something changed.
6. Audit: `narrative.created`, `narrative.claim_added`, `topic.created`,
   `narrative.recommendation_changed`, `narrative_engine.run`.

Re-running with no new data changes nothing (idempotent). Claims added by an analyst are never
removed by the engine.

Triggers: after every submission pipeline run, after every review decision, on
`POST /narratives/analyze`, and periodically via Celery beat (`BNIP_NARRATIVE_INTERVAL_MINUTES`).

## 5. Activity metrics

| Metric | Definition |
|---|---|
| **Claim velocity** | `rate_7d` = occurrences in the last 7 days / 7 (per day); `rate_24h`; `acceleration` = occurrences(last 7d) − occurrences(previous 7d). |
| **Observation growth** | For each channel and metric, latest value vs the latest value ≥ 7 days earlier; growth = Σ max(0, Δ) / max(1, Σ earlier). |
| **Momentum** (0–1) | `0.5·sat(rate_7d, 1.0) + 0.3·sat(max(0, acceleration), 5) + 0.2·sat(obs_growth, 1.0)`, where `sat(x, k) = min(1, x/k)`. |
| **Recurring claim** | Occurrences split into bursts wherever a gap > 7 days separates them. `recurring = bursts ≥ 2`. |
| **Emerging topic** | `recent` = topic claims in the last 7 days; `baseline` = mean weekly count over the previous 4 weeks. Emerging if `recent ≥ 3` and `recent ≥ 2·baseline + 1`. |

Levels: LOW < 0.33 ≤ MEDIUM < 0.66 ≤ HIGH.

## 6. Evidence status and strength (verified layer only)

Only **human-approved** fact-checks count (latest APPROVE decision's `final_classification`).

| Evidence status | Rule (over checkable claims, i.e. not OPINION / PREDICTION / SATIRE) |
|---|---|
| `NOT_CHECKABLE` | no checkable claims |
| `PENDING_VERIFICATION` | no approved fact-check yet |
| `CONTESTED` | approved classifications include both false-ish {FALSE, MISLEADING, OUT_OF_CONTEXT} and true-ish {TRUE, MOSTLY_TRUE} |
| `VERIFIED_FALSE` | approved determinations are all false-ish |
| `VERIFIED_TRUE` | approved determinations are all true-ish |
| `UNRESOLVED` | only UNVERIFIED / INSUFFICIENT_EVIDENCE were approved |

**Evidence strength** (0–1) = mean confidence of the approved determinative assessments ×
(approved checkable claims / checkable claims). It is 0 for PENDING, UNRESOLVED and NOT_CHECKABLE.

## 7. Public interest, harm, uncertainty, coverage

**Public-interest indicators** (aggregate only):
- `distinct_submissions`: separate times the material reached the desk;
- `distinct_origins`: distinct public origin domains or publishers of those submissions;
- `channels`: distinct channels with observations;
- `reach`: Σ latest observation value per (channel, metric).

`public_interest = 0.3·sat(distinct_origins, 5) + 0.2·sat(distinct_submissions, 10) + 0.2·sat(channels, 4) + 0.3·min(1, log10(1+reach)/6)`.

**Potential harm** is assessed by an analyst: category (`NONE`, `PUBLIC_HEALTH`,
`PUBLIC_SAFETY`, `ELECTORAL_PROCESS`, `COMMUNAL_HARMONY`, `FINANCIAL_FRAUD`, `OTHER`) and severity
(`UNASSESSED`, `NONE`, `LOW`, `MEDIUM`, `HIGH`, scored 0 / 0.33 / 0.66 / 1). A rationale is required
for LOW and above. Harm is about **real-world consequences** (health, safety, the mechanics of
voting, violence, fraud), never about which side a narrative helps. The engine adds non-binding
**harm signals** from a fixed keyword lexicon (e.g. "polling booth", "vaccine", "riot") to prompt an
assessment. Signals never set severity.

**Uncertainty** (0–1) = `0.6·unverified_share + 0.25·conflict + 0.15·harm_unknown`, where
`unverified_share` = checkable claims without an approved determination / checkable claims,
`conflict` = 1 if CONTESTED, and `harm_unknown` = 1 if severity is UNASSESSED.

**Existing response coverage** (0–1): +0.6 if we have a FACT_CHECK, CORRECTION or CLARIFICATION
response; +0.3 if there is an EXTERNAL_FACT_CHECK response or FACT_CHECK-type evidence; +0.1 for a
CONTEXT_NOTE; capped at 1. Coverage is **halved** if ≥ 3 new occurrences appeared after the latest
response (stale).

## 8. Response recommendation (`recommend.py`, `rec-v1`)

Inputs: evidence status, public relevance (= public interest), momentum, potential harm,
uncertainty, existing response coverage. The first matching rule wins, and the rule trace is
stored and shown:

| # | Condition | Recommendation |
|---|---|---|
| 1 | harm HIGH and momentum ≥ MEDIUM | **ESCALATE** |
| 2 | harm HIGH (momentum LOW) | **INVESTIGATE** if evidence is not verified, else rule 3+ |
| 3 | VERIFIED_FALSE and coverage ≥ 0.7 | **MONITOR** (already addressed) |
| 4 | VERIFIED_FALSE and (relevance ≥ MEDIUM or momentum ≥ MEDIUM or harm ≥ MEDIUM) | **CORRECT** |
| 5 | VERIFIED_FALSE | **MONITOR** |
| 6 | CONTESTED | **RESPOND** (publish context) if relevance or momentum ≥ MEDIUM, else **INVESTIGATE** |
| 7 | PENDING_VERIFICATION or UNRESOLVED, with relevance, momentum or harm ≥ MEDIUM, or uncertainty ≥ 0.66 | **INVESTIGATE** |
| 8 | PENDING_VERIFICATION or UNRESOLVED | **MONITOR** |
| 9 | VERIFIED_TRUE and relevance ≥ HIGH and momentum ≥ MEDIUM and coverage < 0.3 | **RESPOND** (accurate information is in demand) |
| 10 | VERIFIED_TRUE or NOT_CHECKABLE, with relevance or momentum ≥ MEDIUM | **MONITOR** |
| 11 | otherwise | **IGNORE** |

Harm UNASSESSED is treated as "unknown", never as LOW for escalation. It raises uncertainty, and
rule 7 sends unverified, relevant narratives to INVESTIGATE.

**Suggested status:** ESCALATE → INVESTIGATE (flagged as escalated); INVESTIGATE / RESPOND /
CORRECT / MONITOR map to the same status; IGNORE → ARCHIVED if there has been no activity for 30
days, else MONITOR. A narrative with coverage ≥ 0.7, momentum LOW and VERIFIED status → RESOLVED.

## 9. Relationship graph

Undirected edges between narratives, recomputed every run:

| Type | Rule | Weight |
|---|---|---|
| `SIMILAR` | centroid cosine in [RELATION_SIMILARITY, NARRATIVE_SIMILARITY) | cosine |
| `SAME_TOPIC` | same topic | 0.5 |
| `SHARES_ENTITY` | share a SUBJECT/MENTIONED entity of type PERSON, ORGANIZATION, GOVERNMENT_BODY or MEDIA_OUTLET (never SPEAKER, never PLACE) | Jaccard of entity sets |
| `SHARES_EVIDENCE` | member claims' evidence cites the same source document | count / max count |
| `CONTRADICTS` | similarity ≥ RELATION_SIMILARITY and one is VERIFIED_TRUE while the other is VERIFIED_FALSE | cosine |

## 10. Historical claim matching

`GET /claims/{id}/history` returns earlier claims (`seen_at` before this claim's, or created
earlier) with cosine ≥ `HISTORY_MATCH_SIMILARITY`, sorted by similarity. Each carries its approved
classification (if any), review date and narrative. Matches with an approved fact-check let
reviewers reuse verified work; they never auto-classify the new claim.

## 11. Narrative status workflow (human-only transitions)

| From | To |
|---|---|
| EMERGING | MONITOR, INVESTIGATE, RESPOND, CORRECT, ARCHIVED |
| MONITOR | INVESTIGATE, RESPOND, CORRECT, RESOLVED, ARCHIVED |
| INVESTIGATE | MONITOR, RESPOND, CORRECT, RESOLVED, ARCHIVED |
| RESPOND | MONITOR, CORRECT, RESOLVED |
| CORRECT | MONITOR, RESOLVED |
| RESOLVED | MONITOR, ARCHIVED |
| ARCHIVED | MONITOR |

Each change needs a note and is audited. New claims joining a RESOLVED or ARCHIVED narrative set
`reactivated` in the next metrics snapshot (shown in the UI); the status itself does not change.
