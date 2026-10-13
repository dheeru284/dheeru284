# EpohTech BizDev — lead discovery, outreach and appointment automation

This is a business-development system for **EpohTech Private Limited**. It finds and qualifies prospects with traceable evidence, drafts personalised outreach from verified facts only, puts every outbound message behind an approval and safety pipeline, follows up, and books Dubai or remote meetings.

It runs two campaigns:

- **Campaign A (Dubai):** in-person meetings around 27 Nov 2026. The default window is 23 Nov – 4 Dec and is configurable.
- **Campaign B (remote):** contract, freelance and subcontracting work that can be delivered from India.

> **State on delivery:** every external integration runs as a **mock**. Live sending is **off** and needs two independent switches. See [docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md) for what is simulated and what is live.

## Quick start (local, SQLite)

```bash
pip install -r requirements.txt
python -m bizdev.cli gen-keys > .env           # SECRET_KEY + TOKEN_ENCRYPTION_KEY
echo "DATABASE_URL=sqlite:///./bizdev.db" >> .env
set -a; . ./.env; set +a
alembic upgrade head                           # create schema
python -m bizdev.cli create-admin you@epohtech.example   # prompts for password (>=12 chars)
python -m bizdev.cli seed-demo                 # optional: SYNTHETIC demo data
uvicorn bizdev.web.app:app --port 8000         # dashboard at http://localhost:8000
python -m bizdev.cli worker --interval 60      # in a second shell: follow-ups, dispatch, reminders, inbox
```

## Production (Docker + Postgres)

```bash
cp .env.example .env    # fill in values; generate keys with: python -m bizdev.cli gen-keys
docker compose up -d --build
docker compose exec web python -m bizdev.cli create-admin you@epohtech.example
```

The web port binds to `127.0.0.1`. Put it behind a TLS reverse proxy (Caddy or nginx) and set `OAUTH_REDIRECT_BASE=https://your-host`. That also turns on the `Secure` flag for the session cookie.

**Backups:** run a nightly `pg_dump -Fc bizdev > bizdev-$(date +%F).dump` and keep 14 days. To restore: `pg_restore -c -d bizdev file.dump`. Test a restore once before launch. **Retention:** suppression records are kept indefinitely so that opt-outs keep working. Other contact data can be deleted per organization; the cascade covers contacts and evidence.

## Tests

```bash
python -m pytest -q     # 41 tests; all integrations mocked, nothing is sent
```

The test names map to acceptance criteria 1–17 (`test_01_…` to `test_17_…`). There are also end-to-end tests that go through the HTTP layer: login, CSRF, CSV import → draft → approve → dry-run dispatch, and every page rendering.

## Connecting accounts securely

1. **Google (Gmail + Calendar).** Create an OAuth client (Web) in Google Cloud Console. Add the redirect URI `${OAUTH_REDIRECT_BASE}/oauth/google/callback`. Put the client ID and secret in `.env` and set `EMAIL_PROVIDER=gmail` and `CALENDAR_PROVIDER=gcal`. Then go to **Settings → Connect Google**. The scopes requested are `gmail.send`, `gmail.compose`, `gmail.readonly`, `calendar.freebusy` and `calendar.events`. Tokens are stored only as Fernet ciphertext. You never paste a token anywhere.
2. **Outlook / Microsoft 365.** The adapter interface (`EmailProvider`) is ready, but a Graph adapter is **not implemented yet**.
3. **LinkedIn.** Manual send only. See `bizdev/integrations/linkedin.py` for the reasoning: messaging needs a partner contract.
4. **Apollo.** Set `APOLLO_API_KEY`, and only if your plan permits API use. Apollo records count as *directory listings*, not as evidence of an active project.

## Enabling approved automation

1. Complete **Onboarding**. The readiness table shows what blocks each action.
2. Under **Settings → approval.policy**, choose one of:
   - `manual_every_message` (the default),
   - `approve_new_contact`: you approve the first message per contact, and its follow-ups then auto-approve within the limits,
   - `approved_segments`, with `approval.segments` such as `["staffing_agency:AE"]`.
3. Set `ALLOW_LIVE_SEND=true` in the environment and restart.
4. Under **Settings**, type `I AUTHORIZE LIVE SENDING`.
5. **EMERGENCY STOP** cancels every queued dispatch and follow-up job immediately.

Replies about pricing, contracts, legal terms, proposals or referrals, plus ambiguous replies and anything that looks like prompt injection, always go to **NEEDS_REVIEW**. They are never answered automatically.

## Layout

```
bizdev/
  config.py        env settings + default automation rules
  models.py        data model (18 tables)        migrations/  Alembic
  discovery.py     source adapters, dedup, evidence capture
  scoring.py       0–100 score, tiers, evidence-confidence vs commercial score
  messaging.py     templates per org type, A/B/C variants, verified-fact guard, optional LLM polish
  outreach.py      approval, guarded dispatch, limits, quiet hours, follow-ups, reply classification, job queue
  scheduling.py    slots, conflicts, Dubai/IST zones, confirmation, reminders, outcomes
  remote.py        Campaign B: eligibility, flags, applications
  integrations/    email (mock, Gmail), calendar (mock, Google), linkedin (capability gate)
  web/             FastAPI dashboard
docs/              architecture, compliance, launch checklist, sample report
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Automatic lead import
Drop CSV files into `leads_inbox/`. The worker imports each new file once and writes drafts for Tier A/B leads. With `--pull-leads`, the worker also fetches **only** `leads_inbox/` from the git remote every cycle, so lead batches pushed to the branch arrive on their own without any code being pulled.
```bash
python -m bizdev.cli worker --interval 300 --pull-leads
```
