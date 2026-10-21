# Operations

## Deploy
1. Managed Postgres 14+ (with `btree_gist` available), private S3-compatible bucket, secrets manager.
2. Set env per `.env.example` with real providers; production refuses mock adapters.
3. `docker build -t homenurse .` → run `npx prisma migrate deploy` as a release step → start container (`node server.js`, port 3000).
4. Schedule `npm run jobs:run` every 5 minutes (reminders, credential expiry, SMS dispatch with retries).
5. Configure Razorpay webhook → `POST /api/v1/payments/webhook`.
6. Health check: `GET /api/v1/health`.
7. Never run `db:seed` in production (it refuses).

## Backup & recovery
- Enable provider point-in-time recovery (≥7 days) + daily logical dumps: `pg_dump -Fc "$DATABASE_URL" > backup.dump`, stored encrypted in a separate account/region.
- Restore drill quarterly: `pg_restore -d "$NEW_DB" --no-owner backup.dump`, run `prisma migrate status`, run e2e smoke against it.
- Object storage: enable versioning + cross-region replication.
- RPO/RTO targets to be set by the business.

## Observability
- JSON logs to stdout (redacted); ship to your log platform. Error-reporting hook point: `logger.error` in `src/lib/api.ts`.
- Booking event history: `AppointmentStatusHistory`; notifications: `Notification.status/attempts/lastError`; payments: `Payment`, `WebhookEvent`, `Refund`; security: `AuditLog`.

## Migrations
`npx prisma migrate dev --name <change>` locally; review SQL; `migrate deploy` in CI/CD. The exclusion constraints live in `20261021120000_booking_integrity`.
