# HomeNurse India (working name)

Marketplace for booking **verified registered nurses at home** across Indian cities, plus **serviced apartments near hospitals**. Next.js 15 + TypeScript modular monolith, PostgreSQL via Prisma.

> Non-emergency service. Not legally, clinically or security reviewed. See [docs/LAUNCH_BLOCKERS.md](docs/LAUNCH_BLOCKERS.md) before any production use.

## Quick start

```bash
cp .env.example .env            # set DATABASE_URL; set DEV_EXPOSE_OTP="true" for local login
docker compose up -d db         # or use any Postgres 14+
npm ci
npx prisma migrate deploy
npm run db:seed                 # fictional demo data — refuses to run in production
npm run dev                     # http://localhost:3000
```

Demo logins (OTP is shown on screen when `DEV_EXPOSE_OTP=true`):

| Role | Phone |
|---|---|
| Patient/family | +919000000010 |
| Nurse (approved) | +919000000101 / 102 / 103 |
| Nurse (pending — not bookable) | +919000000105 |
| Admin | +919000000001 |
| Compliance officer | +919000000002 |
| Accommodation partner | +919000000020 |

All demo people, nurses, hospitals and properties are fictional and badged "Demo data" in the UI.

## Checks

```bash
npm run lint && npm run typecheck
npm test                         # 79 unit+integration tests against a real Postgres (TEST_DATABASE_URL, default homenursing_test)
npm run build
BASE_URL=http://localhost:3000 node tests/e2e/acceptance.mjs   # 27 HTTP acceptance checks against a seeded dev server
npm run jobs:run                 # reminders, credential expiry, notification dispatch (schedule every 5 min)
```

## Docs
- [Architecture](docs/ARCHITECTURE.md) — modules, matching engine, booking integrity, providers
- [API](docs/API.md) — `/api/v1` routes, error format
- [Security checklist](docs/SECURITY.md)
- [Regulatory-readiness checklist](docs/REGULATORY_READINESS.md) — for Indian legal counsel
- [Operations: deploy, backup, recovery](docs/OPERATIONS.md)
- [Launch blockers & known gaps](docs/LAUNCH_BLOCKERS.md)
