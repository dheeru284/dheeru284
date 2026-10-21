# Status, known gaps and launch blockers

## Implemented and tested
- 96 unit/integration tests against real Postgres (`npm test`), 8 Playwright browser journeys on mobile + desktop (`npm run e2e`), 27 HTTP acceptance checks (`tests/e2e/acceptance.mjs`). All run in CI.
- All 20 MVP acceptance scenarios from the brief.
- Production adapters exist for every provider (see ARCHITECTURE.md), but **none has been exercised against the live service** — that needs your accounts.

## Launch blockers (cannot be solved in code)
1. **Legal**: every item in REGULATORY_READINESS.md; final privacy/terms/refund text (current pages are drafts); grievance officer appointment.
2. **Clinical**: a qualified clinician must review service protocols/checklists; invasive services stay off until sign-off is recorded in Admin → Service catalog.
3. **Accounts & keys**: Google Maps (Routes + Geocoding), MSG91 with DLT-registered templates, Razorpay (and the marketplace settlement model), S3 bucket, SMTP, optional WhatsApp Business.
4. **Live verification**: validate travel estimates against real trips in launch cities; end-to-end test each provider in a staging environment.
5. **Security**: independent penetration test; admin MFA; field-level encryption of clinical notes; malware scanning on uploads; secrets manager.
6. **Operations**: verification SOP against council portals, support staffing, incident escalation, payout process.
7. **Languages**: Hindi strings and templates need native review; other regional languages need translation.

## Remaining known gaps (smaller)
- Map is a "check pin" link plus geocoder search, not an embedded draggable map.
- Recurring series are independent visits grouped by `recurrenceGroupId` (no series-level edit).
- Deposit refunds after checkout are manual via Admin → Payments (no automatic deposit release).
- OpenAPI spec documents paths, methods and permissions; request bodies point to the Zod schema rather than being expanded.
- Settlements create payout *records*; they don't call a payout API.
