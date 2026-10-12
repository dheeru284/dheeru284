# Architecture

## Stack choices, and where they differ from the brief

| Brief suggested | Built | Why |
|---|---|---|
| Next.js frontend | Server-rendered Jinja dashboard inside FastAPI | One language and one deployable unit for a one-admin tool. No client-side token handling. A strict CSP is easy. The JSON API (`/api/metrics`) leaves room for a SPA later. |
| Celery + Redis | DB-backed job table (`jobs`) + `bizdev.cli worker` | Volume is tens of messages a day. A transactional DB queue gives idempotency (`dedupe_key`), dead letters (`status=DEAD`) and the emergency stop in the same transaction as the state change. It also means one less service to secure. Swap it out if volume grows 100×. |
| PostgreSQL | PostgreSQL in prod, SQLite for dev/tests | SQLAlchemy 2 plus Alembic, with the same migrations for both. |

## Flow

```
sources (CSV research, Apollo, manual) ─► discovery.ingest ─► dedup (domain / normalised name / email / LinkedIn)
      └─ untrusted.clean_text + injection scan                └─► Evidence rows (source_url, date, is_inference)
                                                                   └─► scoring.qualify ─► tier A/B/C
messaging.draft (verified facts only, variant rotation, content-hash dedup) ─► DRAFTED
   └─ human approve / policy auto-approve ─► APPROVED ─► jobs: dispatch
outreach.dispatch guards, in order:
   halted? → approved? → suppressed? → replied (follow-ups)? → rate limits → quiet hours/weekend (recipient TZ)
   → LinkedIn ⇒ MANUAL_PENDING → dry-run? ⇒ DRY_RUN → provider.send (idempotency key) ⇒ SENT | retry w/ backoff | FAILED
SENT intro ─► follow-up jobs (day 4/9/15, configurable) ─► re-checked at run time, drafted, approval again
inbox poll ─► classify reply ─► unsubscribe/not-interested ⇒ suppress + cancel; interested ⇒ REPLIED; pricing/legal/ambiguous ⇒ NEEDS_REVIEW
scheduling: propose 2–3 slots (calendar busy + DB appointments + buffer) ─► confirm only with prospect_agreed (and a location for in-person) ─► calendar event + reminders
```

## Lead state machine

`DISCOVERED → QUALIFIED → MESSAGE_DRAFTED → APPROVED → SENT → REPLIED → MEETING_PROPOSED → MEETING_BOOKED → COMPLETED`. The side states are `NEEDS_REVIEW, BOUNCED, FOLLOW_UP_DUE, NOT_INTERESTED, UNSUBSCRIBED, DO_NOT_CONTACT, CLOSED, FAILED`.

A message has its own status: `DRAFTED → APPROVED → QUEUED → (DRY_RUN | MANUAL_PENDING | SENT) → ACKNOWLEDGED`, or it ends in `BOUNCED / FAILED / SUPPRESSED / CANCELLED / REJECTED`. LinkedIn needs a separate draft → queued → manual-pending → sent → acknowledged path, and these statuses provide it.

## Safety invariants (each one is tested)

- External sending happens only if `ALLOW_LIVE_SEND` (env) **and** `system.live_send_authorized` (DB, set by an admin typing a confirmation phrase) are both true.
- A message cannot be dispatched without `approved_by`. The auto-approve policies never cover first contact under `approve_new_contact`, unverified contacts, or replies that need judgement.
- Opt-outs, bounces and "not interested" replies create `suppressions` rows. Those rows are checked at dispatch time, not only at draft time.
- When an integration raises, the message ends as `FAILED` or `QUEUED` (retry), never `SENT`. A provider response with no message ID counts as a failure.
- Retrieved and inbound text is cleaned, capped and scanned for injection. It is only passed to an LLM inside a randomised fence, and an LLM rewrite that adds claims is discarded. No code path turns untrusted text into an action.
- Message generation refuses unverified claims (certifications, headcounts, "clients include", guarantees) unless they appear in the verified profile.
- The Dubai trip is mentioned only for Campaign A and only before the window ends. In-person slots are clamped to the window, and to tomorrow or later.

## Data model

There are 18 tables in `bizdev/models.py`, and the migration lives in `migrations/versions/`. They cover users, company profile, service offerings, organizations, contacts, evidence, opportunities (jobs/projects), applications, assessments, campaigns, threads, messages, suppressions, consents, jobs, appointments, calendar events, integration accounts, automation rules and audit logs. Dedup relies on unique keys for org domain, contact email, contact LinkedIn URL, (org, source_url, signal) for evidence, opportunity source_url, message idempotency key, and job dedupe key.
