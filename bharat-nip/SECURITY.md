# Security, Safety and Responsible Use

## 1. Threat model (summary)

| Asset | Threats | Primary controls |
|---|---|---|
| Integrity of verdicts | Manipulated evidence, prompt injection via sources, biased tiering, insider tampering | Quote verification, data/instruction separation, audited tier changes with rationale, four-eyes review, hash-chained audit log |
| Audit trail | Deletion or alteration to hide changes | Append-only trigger, hash chain, verification endpoint, DB role separation (Phase 3) |
| User accounts | Credential theft, privilege escalation | Argon2 hashing, short-lived JWTs, RBAC on every route, audited role changes |
| Platform as a weapon | Use for disinformation, profiling, astroturfing | Prohibited capabilities are not built (§5); human approval for all outputs; no publishing in M1 |
| Infrastructure | SSRF via URL fetching, secrets leakage, dependency compromise | URL allowlist and private-IP blocking, env-only secrets, lockfiles and dependency audit |

## 2. Application security controls

- **Authentication** (Phase 1a): local accounts, Argon2id, JWT (HS256 in
  development; asymmetric keys in production), 30-minute expiry. OIDC in Phase 3.
- **Authorization:** role checks as FastAPI dependencies on every route, plus
  object-level checks (owners only see their own submissions; reviewer ≠ submitter).
- **Input validation:** Pydantic schemas with length limits on every field;
  `raw_text` ≤ 20,000 chars; source `content_text` ≤ 2 MB.
- **Errors:** problem+json without stack traces outside development.
- **CORS:** explicit allowlist (`BNIP_CORS_ORIGINS`).
- **Rate limiting** (Phase 3): per-user limits on submission and ingest.
- **Secrets:** environment variables only. `.env` is git-ignored; `.env.example`
  contains no real values. `BNIP_JWT_SECRET` must be set (≥32 bytes) when
  `BNIP_ENV=production`, or startup fails.
- **SQL:** SQLAlchemy only, never string-built SQL. Vector and full-text
  queries use bound parameters.
- **Outbound fetching** (when URL retrieval arrives): scheme allowlist
  (`https`), block private/link-local/loopback ranges after DNS resolution,
  size and time limits, no redirects to blocked ranges.
- **Dependencies:** `uv.lock` and `package-lock.json` committed; `pip-audit`
  and `npm audit` in CI (Phase 3).

## 3. AI-specific controls

- **Prompt injection:** source and submission text are always passed as
  delimited data blocks. The system prompt says that content is untrusted.
  Agents have no tools and no write access, so injected instructions can at
  most corrupt one structured proposal, which then has to pass guardrails,
  the critic, and a human.
- **Output validation:** strict Pydantic schemas; invalid output is recorded
  and retried with a bound, never coerced.
- **Hallucinated sources and citations:** impossible by construction. Agents
  can only reference IDs they were given, and quotes must be verbatim.
- **Provenance:** every call recorded in `ai_runs`. This lets us find every
  output affected by a model or prompt issue.
- **Mock provider:** refused in production; visibly labeled elsewhere.

## 4. Audit log integrity

- Append-only via a DB trigger (UPDATE/DELETE) and a TRUNCATE trigger.
- Each event hashes its predecessor: `hash = sha256(prev_hash ‖ canonical_json(fields))`.
- `GET /audit-events/verify` recomputes the chain.
- Phase 3: the app's DB role gets INSERT/SELECT only on `audit_events`;
  migrations run under a separate owner role; the latest chain head is
  periodically anchored outside the database.

## 5. Responsible use: prohibited capabilities

These are **design constraints**, not configuration flags. Pull requests that
add them must be rejected.

1. **No voter-level political profiling.** No storing, inferring or scoring of
   private individuals' political views, affiliations, demographics or
   persuadability. No microtargeting lists. Analytics are aggregate, over public content.
2. **No fake personas or impersonation.** No generation or operation of
   accounts posing as real or invented people, and no content attributed to
   people who didn't say it.
3. **No deceptive bots or astroturfing.** No coordinated inauthentic
   behaviour, simulated grassroots activity, or undisclosed automated posting.
4. **No automated publishing without human approval**, and only to accounts
   the organization openly operates (Phase 6).
5. **No suppression tooling.** The platform doesn't build mass-reporting,
   harassment or doxxing features.
6. **No partisan rules.** No code, prompt or configuration may condition
   verdicts, rankings or tiers on political affiliation.

## 6. Data protection

- Personal data is limited to platform users (name, email, role) and
  public-figure attribution. India's Digital Personal Data Protection Act, 2023
  is the reference framework for handling user data.
- Ingested sources must be public documents.
- Logs never contain passwords, tokens or full JWTs.

## 7. Reporting vulnerabilities

Report privately to the project maintainer (see the repository owner's
profile). Don't open public issues for security problems.
