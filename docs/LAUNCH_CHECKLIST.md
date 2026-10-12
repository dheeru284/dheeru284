# Launch checklist: simulated vs live

## What is real today, and what is simulated

| Capability | Status | Notes |
|---|---|---|
| Data model, migrations, dedup, scoring, evidence capture | **Working**, tested | |
| Message generation (templates, variants, fact guard) | **Working**, tested | LLM polishing is optional and untested against a live API |
| Approval workflow, limits, quiet hours, idempotency, emergency stop | **Working**, tested | |
| Follow-up engine, reply classification, suppression | **Working**, tested (mock inbox) | Classifier is rule-based. Review NEEDS_REVIEW items |
| Scheduling (slots, conflicts, TZ, reminders, outcomes) | **Working**, tested (mock calendar) | |
| Remote opportunity pipeline | **Working**, tested | Opportunities are entered manually or by CSV. No crawler |
| Dashboard + auth + CSRF | **Working**, tested end to end | |
| Gmail send/draft/read | **Code written, NOT verified live** | Needs a Google OAuth client and a consent test |
| Google Calendar free/busy + events | **Code written, NOT verified live** | Same |
| Outlook / Microsoft Graph | **Not implemented** | Adapter interface exists |
| Apollo people search | **Code written, NOT verified live** | Needs a key and a plan that allows API use |
| Automated web/job-board discovery | **Not implemented** | This build environment's proxy blocked job sites (see job-tracker.md). Leads currently come from CSV or manual research |
| LinkedIn messaging | **Manual by design** | No public API for it |

## Steps to go live (in order)
1. Fill in Onboarding: website, description, sender name/title/email, postal address, delivery capacity, and verified facts.
2. Confirm the actual Dubai travel dates in Onboarding. Then set `availability` in Settings and confirm it, or connect Google Calendar.
3. Deploy with Postgres behind TLS. Create the admin. Remove `ADMIN_PASSWORD` from env.
4. Connect Google. Send **one test email to yourself** with live sending enabled and check it in Gmail (threading, signature, List-Unsubscribe).
5. Import 10–20 researched leads (CSV with real `source_url`s). Review scores and evidence.
6. Keep `manual_every_message` for the first 2 weeks. Approve each message.
7. Then consider `approve_new_contact` for follow-ups only.
8. Weekly: check the audit log, NEEDS_REVIEW items, bounces and dead jobs.

## Human actions the system will never take for you
Negotiating rates or terms, signing anything, submitting job applications, booking travel, assuming meeting locations, and sending LinkedIn messages.
