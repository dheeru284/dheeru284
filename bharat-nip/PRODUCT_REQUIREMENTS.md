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

Each assessment also carries a **confidence** of `LOW`, `MEDIUM` or `HIGH`.
These are deliberately coarse categories; the system does not report fake
precision like "87.3% true".

## 5. Milestone 1: the evidence pipeline (functional requirements)

**FR-1 Submission.** An authenticated user submits text (required, up to 20,000
characters) with optional source URL, statement date, speaker (an existing
entity), language (default `en`) and context note. An `Idempotency-Key` header
prevents duplicate submissions.

**FR-2 Claim extraction.** The system splits a submission into one or more
atomic claims and classifies each as `FACTUAL`, `OPINION`, `PREDICTION`,
`SATIRE` or `UNCLEAR`, with a check-worthiness flag. Analysts can edit or add
claims manually; manual edits are audited and marked as human-authored.

**FR-3 Source corpus and retrieval.** Analysts ingest sources (title, URL,
publisher, type, published date, full text). The system stores an immutable
snapshot with a SHA-256 hash, splits it into chunks, and embeds them. For each
checkable claim the system retrieves candidate chunks (vector similarity plus
keyword search) and records every retrieval result with its score and query.

**FR-4 Evidence records.** From the retrieved chunks the system proposes
evidence: an exact quote, its offsets in the source, its stance (`SUPPORTS`,
`REFUTES`, `MIXED`, `CONTEXT`, `NOT_RELEVANT`) and a one-sentence rationale.
Quotes that are not exact substrings of the stored snapshot are rejected and
the rejection is logged. Analysts can add evidence manually, under the same
quote-verification rule.

**FR-5 Evidence ranking.** Evidence is scored by a deterministic, versioned
function of publisher reliability tier, source type (primary vs secondary),
retrieval relevance, recency relative to the statement date, and independence
(duplicates from the same publisher are discounted). Score components are
stored and shown. Reliability tiers are set by admins against a published
methodology (transparency, corrections policy, primary-data status), **never
by political alignment**, and every tier change is audited with a rationale.

**FR-6 Factual assessment.** The assessor agent receives the *blinded* claim
text, the statement date, and ranked evidence. It returns a verdict,
confidence, rationale, missing-context note, and the evidence IDs it relied
on. Guardrails:
- a checkable claim with no `SUPPORTS`/`REFUTES`/`MIXED`/`CONTEXT` evidence → `INSUFFICIENT_EVIDENCE`, without calling the LLM;
- every cited ID must belong to this claim's evidence, or the output is invalid;
- `TRUE`, `MOSTLY_TRUE`, `FALSE`, `MISLEADING` and `OUT_OF_CONTEXT` require at least one citation.

**FR-7 Structured critic.** A separate critic agent checks the assessment
against a fixed checklist: citation validity, verdict–evidence consistency,
overclaiming, missing context, attribution leakage (did speaker identity
influence the reasoning?), and verdict-definition compliance. Outcome: `PASS`,
`REVISE` (with specific issues) or `ESCALATE`. `REVISE` loops back to the
assessor at most `MAX_REVISION_ROUNDS` times (default 2); then it escalates.

**FR-8 Human review.** Every assessment creates a review task. Escalations,
`LOW` confidence, `INSUFFICIENT_EVIDENCE` and `UNVERIFIED` get higher priority.
A reviewer sees the claim, the evidence with source links, the assessment, the
critique and the AI provenance. They decide `APPROVE`, `AMEND` (choose a
different verdict, with a required note), `REJECT`, or `REQUEST_MORE_EVIDENCE`.
The person who made the submission cannot decide its review.

**FR-9 Audit log.** Every state change (submission, extraction, retrieval,
evidence accept/reject, ranking, assessment, critique, review decision,
tier change, user/role change) writes an append-only, hash-chained audit event
in the same transaction. Admins can verify the chain.

**FR-10 Provenance view.** For any assessment, a user with access can see the
full chain: claim → evidence → source chunk → source snapshot, and every
`ai_run` with its provider, model, prompt ID/version/hash and parameters.

## 6. Later capabilities (not in Milestone 1)

Order and gating are in [ROADMAP](ROADMAP.md).

- **Narrative intelligence:** cluster related claims into narratives and track
  their volume and spread over time across *public* sources, in aggregate only.
- **Communications support:** draft explainers or corrections that use only
  approved assessments and cite their evidence. Drafts are clearly labeled as
  AI-assisted, and a human must approve them.
- **Publishing integrations:** post human-approved content to the
  organization's own official, clearly-identified accounts. Only after the
  pipeline is proven in production.

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| Traceability | 100% of approved assessments have ≥1 citation or a verdict exempt from citation (`INSUFFICIENT_EVIDENCE`, `UNVERIFIED`, `OPINION`, `PREDICTION`, `SATIRE`). |
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
