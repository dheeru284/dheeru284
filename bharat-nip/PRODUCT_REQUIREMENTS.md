# Product Requirements — Bharat Narrative Intelligence Platform

## 1. Vision

Give people working in public life (journalists, researchers, civic
organizations, and the communications teams of parties, governments and
NGOs) a tool that tells them **what the evidence actually says** about a claim,
with every conclusion traceable to its sources. Then, and only then, help them
communicate accurately.

## 2. Non-negotiable product rules

1. **Evidence decides, not affiliation.** A claim gets the same verdict
   whoever said it. The system never treats a claim as false because of its
   source's party, ideology, nationality or organization, and never as true
   because it came from the user's own organization.
2. **Say "we don't know" when we don't.** Insufficient evidence produces
   `INSUFFICIENT_EVIDENCE` or `UNVERIFIED`, never a guess.
3. **No fabrication.** The system never invents sources, quotes, evidence or
   statistics. Every factual statement it outputs is traceable to stored evidence.
4. **Humans approve.** No assessment is final without a human reviewer, and no
   one approves their own work, human or agent.
5. **Prohibited capabilities.** The platform will not include:
   - voter-level or individual-citizen political profiling or targeting;
   - fake personas, sockpuppets, impersonation or deceptive bots;
   - fabricated grassroots activity (astroturfing) or coordinated inauthentic behaviour;
   - automated publishing without human approval.

## 3. Users and roles

| Role | Can |
|---|---|
| `SUBMITTER` | Submit claims; see their own submissions and the final, approved results. |
| `ANALYST` | Everything a submitter can, plus ingest sources, view full pipeline detail (evidence, AI runs, critiques), and re-run stages. |
| `REVIEWER` | Everything an analyst can, plus claim and decide review tasks. Cannot decide a task whose submission they made. |
| `ADMIN` | Manage users and publisher reliability tiers; view audit and chain verification. Admin actions are audited like everything else. |

## 4. Verdict taxonomy

The verdict set is closed. Definitions are part of the assessor and critic
prompts and of reviewer guidance; changing them requires a prompt version bump.

| Verdict | Definition | Typical evidence condition |
|---|---|---|
| `TRUE` | The claim is accurate and nothing significant is missing. | Strong, direct, independent evidence supports it; no credible refutation. |
| `MOSTLY_TRUE` | Accurate, but needs clarification or has a minor inaccuracy that doesn't change its thrust. | Support with small discrepancies (e.g. a rounded figure, slightly wrong date). |
| `MISLEADING` | Contains accurate elements but creates a false overall impression (cherry-picking, wrong comparison, conflation). | Evidence supports parts but contradicts the implied conclusion. |
| `OUT_OF_CONTEXT` | Real content (quote, image, figure) presented in a context that changes its meaning. | Evidence of the original context differs materially from the presented one. |
| `FALSE` | The core of the claim is contradicted by evidence. | Strong, direct evidence refutes it. |
| `UNVERIFIED` | Relevant evidence exists but does not settle the claim: it conflicts, or it cannot be corroborated independently. | Mixed or single-source, uncorroborated evidence. |
| `INSUFFICIENT_EVIDENCE` | Not enough relevant evidence was found to assess the claim. | No evidence, or only tangential evidence. **Forced automatically when a checkable claim has zero evidence.** |
| `OPINION` | A value judgment, not a checkable statement of fact. | Determined from claim classification. |
| `PREDICTION` | A statement about the future that can't yet be checked. | Determined from classification; may be re-checked later. |
| `SATIRE` | Intended as parody or humour, and identifiable as such. | Classification plus context (e.g. a known satire publisher). |

Each assessment carries a **confidence** between 0 and 1: how strongly the evidence supports the
classification. It is capped deterministically by what the evidence can bear (for example, at most
0.6 when only one independent origin is cited), and both the agent's raw value and the applied caps
are shown. A confidence of 0 means no evidential determination was made (rule-based
INSUFFICIENT_EVIDENCE, OPINION, PREDICTION, SATIRE).

The system **never forces a classification**: without usable evidence the result is
INSUFFICIENT_EVIDENCE, decided by rule without calling an LLM.

## 5. Milestone 1: the evidence pipeline (implemented in Phase 1)

**FR-1 Submission.** An authenticated user submits one of:
- **text claim**, **article** (body plus optional headline, publisher, URL), **URL** (fetched
  server-side over HTTPS with SSRF protection; HTML and PDF are extracted);
- **image** or **PDF** upload (type checked from the file bytes; PDF text layer extracted; images
  use OCR when the server has `tesseract`, otherwise a human transcription is requested);
- **video metadata** (platform, URL, title, description, uploader, date, and a submitter-supplied
  transcript; video is never downloaded).

Optional fields: speaker entity, statement date, language, context note. An `Idempotency-Key`
prevents duplicates. When no machine-readable text exists, the submission is marked
`NEEDS_TRANSCRIPTION`. The system does not guess text.

**FR-2 Claim extraction.** Material becomes atomic claims, each with: claim ID, text, subject,
predicate, object, time reference and exact date (only if stated), location, entities (with role
speaker / subject / mentioned), original source (submission, type, URL, title, publisher), claim
type, check-worthiness, and `extracted_at`. Claims not grounded in the material are rejected and
audited. The speaker is blinded out of the text used by search, assessment and critique.

**FR-3 Source registry.** Registry entries record category, jurisdiction, authority level,
authority scope (topics), default source type, primary or secondary status, and verification
metadata (status, method, notes, verifier, date, review-due date). It is **not** a permanent
true/false publisher list: authority is scoped and time-limited, requires a written rationale,
counts only while verified and in date, resets on substantive edits, influences ranking (never a
verdict directly), and never uses political alignment as a criterion.

**FR-4 Evidence retrieval.** Behind a `SearchProvider` interface: a mock provider (tests), a
configurable web search provider (self-hosted SearXNG), and the local corpus of documents analysts
ingest. Every query, result and fetch is recorded. Each evidence item records URL, title,
publisher, publication date, retrieval date, content (the immutable source snapshot), source type,
relevance, support/contradiction relationship (stance), directness, and the source's content hash.
Quotes must be found verbatim in the stored source.

**FR-5 Evidence ranking.** Deterministic `rank-v2` with seven factors (source authority,
primary-source status, relevance, recency, directness, corroboration across independent origins,
document quality), with weights and every component stored and shown.

**FR-6 Classification.** One of the ten classifications in §4, with the guardrails in
AI_AGENT_ARCHITECTURE §7.

**FR-7 Result.** A structured JSON result: `classification`, `confidence`, `summary`,
`reasoning`, `supporting_evidence`, `contradicting_evidence`, `missing_information`,
`recommended_action`, plus provenance, guardrails, critic output and review status (API_DESIGN §3).

**FR-8 Critic.** An independent `FactCheckCriticAgent` tries to disprove the assessment. It checks
source quality, outdated evidence, cherry-picking, missing context, incorrect interpretation,
contradictory evidence, unsupported conclusions and attribution leakage. Deterministic findings
are computed first and enforced: a PASS that ignores a high-severity finding is escalated.
REVISE loops back to the assessor at most `MAX_REVISION_ROUNDS` times.

**FR-9 Human review.** Review status is one of `PENDING_REVIEW`, `APPROVED`, `REJECTED`,
`NEEDS_MORE_RESEARCH`. Every claim reaches a human. Escalations and stage failures get top
priority. Reviewers cannot decide on their own submissions. Changing the classification,
rejecting, or requesting more research requires notes. NEEDS_MORE_RESEARCH can be re-run by an
analyst, producing a new assessment revision.

**FR-10 Audit trail.** Append-only, hash-chained events for every claim, source, search,
evidence decision, agent execution, assessment, critic result, revision and human decision,
written in the same transaction as the change. Admins can verify the chain.

**FR-11 Provenance view.** For any result, the claim → evidence → source snapshot chain and every
agent run (provider, model, prompt ID, version and hash) are visible.

## 5a. Phase 2: Narrative intelligence (implemented)

Specified in [NARRATIVE_INTELLIGENCE.md](NARRATIVE_INTELLIGENCE.md):
- narrative detection, topic clustering, emerging-topic and recurring-claim detection;
- claim velocity, evidence strength (approved fact-checks only) and public-interest indicators;
- the relationship graph and historical claim matching;
- a response recommendation for every narrative.

Statuses: EMERGING, MONITOR, INVESTIGATE, RESPOND, CORRECT, RESOLVED, ARCHIVED. Recommendations:
RESPOND, MONITOR, INVESTIGATE, CORRECT, IGNORE, ESCALATE. These are computed from evidence status,
public relevance, momentum, potential harm, uncertainty and existing response coverage. There is
no inference of individual political preference, no voter psychological profiling, aggregate and
public information only, and no persuasion scores.

## 6. Later capabilities (not in Milestone 1)

Order and gating are in [ROADMAP](ROADMAP.md).

- **Communications support:** draft explainers or corrections that use only
  approved assessments and cite their evidence. Drafts are clearly labeled as
  AI-assisted, and a human must approve them.
- **Publishing integrations:** post human-approved content to the
  organization's own official, clearly-identified accounts. Only after the
  pipeline is proven in production.

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| Traceability | 100% of affirmative classifications (TRUE, MOSTLY_TRUE, MISLEADING, OUT_OF_CONTEXT, FALSE) cite ≥1 evidence item, enforced at validation time. |
| Provenance | 100% of LLM outputs have an `ai_runs` row with provider, model, prompt version and hash. |
| Reproducibility | `alembic upgrade head` from empty and `downgrade base` both succeed in CI. |
| Runnability | `main` always passes backend and frontend test suites and builds. |
| Local-first | The full stack runs on a laptop with free software (Postgres, Redis, Ollama). |
| Languages | M1 is English-first. The schema stores `language` on submissions, claims and sources; Indic-language support is on the roadmap. |
| Performance (M1 target) | Submission API p95 < 300 ms (excluding async pipeline). Pipeline throughput is bounded by the LLM; there's no SLA in M1. |

## 8. Success metrics for Milestone 1

- The end-to-end pipeline runs for a submitted claim with both the mock
  provider (CI) and Ollama (manual run).
- Attribution-invariance test suite: identical verdicts when the speaker is swapped.
- Zero evidence rows whose quote is not an exact substring of its source (DB-verified test).
- Reviewer can complete a decision with full provenance visible.
