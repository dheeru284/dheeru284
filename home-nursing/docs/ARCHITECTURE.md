# Architecture

Modular monolith (Next.js App Router). Layers:

| Layer | Location | Rule |
|---|---|---|
| Presentation | `src/app/**/page.tsx`, `src/components` | No business rules; page guards are convenience only |
| API | `src/app/api/v1/**/route.ts` via `route()` in `src/lib/api.ts` | Zod validation, permission check, same-origin check, uniform errors |
| Domain | `src/lib/domain/*` | All business rules + authorization at the service layer |
| Providers | `src/lib/providers/*` | Interfaces for routing, SMS, payments, storage; mock adapters dev-only |
| Persistence | `prisma/schema.prisma`, migrations | Integrity constraints in the DB |

## Nurse matching (`domain/matching.ts`)
1. DB filter: `APPROVED`, not paused, approved eligibility for the service, optional gender.
2. `nurseGate`: verified unexpired registration, all mandatory documents `VERIFIED` and unexpired *at the appointment time*, verified required qualification.
3. `isAvailable`: weekly hours (nurse timezone, default Asia/Kolkata), time-off, existing bookings incl. travel buffer (`blockStart/blockEnd`).
4. Coarse great-circle pre-filter (`fallbackRadiusKm`) — only to avoid routing calls; **never reported as travel time**.
5. Road estimate from the routing provider for the departure time derived from the slot (Google Routes `TRAFFIC_AWARE_OPTIMAL` with `departureTime`).
6. Threshold = min(platform `maxTravelMinutes` (default **120**), nurse's own limit). Optional road-distance cap.
7. Weighted score (travel, Bayesian-shrunk rating, experience, language, reliability) — computed per request, not stored.
8. Booking (`createAppointment`) re-runs every check, then inserts.

Routing failure → estimate `null` → default policy `EXCLUDE`; alternative `INCLUDE_FLAGGED_MANUAL_CONFIRM` shows "unavailable" with no minutes. Nothing is invented. Failures are never cached; cache key includes coordinates and a 15-min departure bucket; changing matching settings clears the cache.

All settings live in `PlatformSetting` (Zod-validated, audited) — editable in Admin → Travel & matching without redeploy. Expansion beyond the limit only when the admin enables it and the patient explicitly asks.

## Booking integrity
- `appointment_no_nurse_overlap`: Postgres `EXCLUDE USING gist (nurseId =, tstzrange(blockStart, blockEnd) &&)` for active statuses. Concurrent requests → exactly one wins (tested with 5 parallel attempts).
- `stay_no_unit_overlap`: same for accommodation units with `daterange(checkIn, checkOut)`; booking tries free units in turn.
- Status transitions use a role-checked state machine and optimistic `updateMany where status = expected`.
- Recurring visits: each occurrence fully validated; conflicts are skipped and reported, never forced.
- Reschedule: retire old → create new (re-validated) → compensate on failure. Not a single DB transaction (documented gap).

## Data visibility
- Nurse sees only locality/city and first name until they accept; then full address + care notes.
- Admin ops view excludes clinical notes; there is no `clinical.read` permission yet (break-glass flow is future work).
- Partners see guest name/phone/dates only.
- Nurse service-origin coordinates never leave the server.

## Providers
| Interface | Dev adapter | Production adapter | Verified against live service? |
|---|---|---|---|
| Routing | `SimulatedRoutingProvider` (labelled) | `GoogleRoutesProvider` (traffic-aware, departure time) | No — tested with mocked HTTP |
| Geocoding | `DevGazetteerGeocoder` (5 demo localities) | `GoogleGeocodingProvider` | No — mocked HTTP |
| SMS/OTP | `MockSmsProvider` | `Msg91SmsProvider` (DLT flow templates) | No — mocked HTTP |
| Email | `MockEmailProvider` | `SmtpEmailProvider` (nodemailer) | No |
| WhatsApp | `MockWhatsAppProvider` | `WhatsAppCloudProvider` (template messages) | No |
| Payments | `MockPaymentProvider` (same HMAC contract) | `RazorpayProvider` (orders, signature, webhooks, refunds) + Checkout.js in UI | No — signature maths tested |
| Storage | `MockStorageProvider` (HMAC URLs) | `S3StorageProvider` (presigned PUT/GET, SSE) | Presigning tested offline; no live bucket |
| Errors | stdout JSON | `ERROR_WEBHOOK_URL` forwarder | — |

`assertProductionSafe` refuses to boot in production with any mock/simulated/dev adapter or missing keys.

## Other flows added in phase 2
- **Prescription authorization**: patient uploads to private storage → staff queue (`authorization.review`) → verified releases the booking to the nurse; rejected keeps it on hold. Views are audited. Staff check documents; they do not make clinical decisions.
- **Atomic reschedule**: old booking retired and new one inserted in one transaction (`beforeInsert` hook); the exclusion constraint sees both.
- **Stays**: pay after partner confirmation (total + deposit), partner blackouts/rate periods/photos/calendar, check-in/out, cancellations route paid stays to a refund-review queue (property policy, not a formula).
- **Settlements**: per-period records for nurses and partners from completed + paid work; finance marks them paid with a payout reference. Reconciliation flags captured-but-unpaid, stale orders, over-refunds.
- **Notifications**: IN_APP/SMS/EMAIL/WHATSAPP with per-language templates, retries (3), SKIPPED when a channel isn't configured; clinical words blocked in non-app templates.
- **Jobs** (`npm run jobs:run`): credential expiry, reminders (24h), expiry of never-accepted requests, notification dispatch, data retention.
- **i18n**: UI chrome + templates per language; English complete, Hindi starter set (needs native review), other languages fall back to English.
- **PWA**: manifest, icon, service worker that caches static assets only (never API responses).
## Medicine delivery
Feature flag `medicine_delivery` exists, is locked off in the admin API, and `/api/v1/medicine` returns `FEATURE_DISABLED`. No code path sells medicines.
