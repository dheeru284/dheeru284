# Status, known gaps and launch blockers

## Works end to end (dev adapters)
All 20 MVP acceptance scenarios are exercised by `tests/e2e/acceptance.mjs` and/or the integration suite, with these caveats: travel times in dev come from a **simulated** provider (labelled in UI); payments use a mock adapter with the real signature contract; SMS is captured locally.

## Launch blockers
1. **Legal review** of every item in REGULATORY_READINESS.md; final privacy/terms/refund text.
2. **Clinical sign-off** of service protocols and checklists; invasive services stay off until recorded.
3. **SMS provider** adapter (DLT-registered) — not implemented; production will not boot without it.
4. **S3 storage** adapter — not implemented; uploads only work with the dev mock.
5. **Google Routes API key** and billing; validate estimates against real trips in launch cities.
6. **Razorpay** account, marketplace/settlement model, live webhook test.
7. Security items unchecked in SECURITY.md (pen test, CSP, admin MFA, encryption of clinical fields).
8. Real operations: verification SOP against council portals, support staffing, incident escalation.

## Known gaps (not blocking a pilot, but real)
- Prescription upload UI + admin authorization queue (API state `AWAITING_AUTHORIZATION` exists; transition is admin-only, no dedicated screen)
- Map-based address picker/geocoding (manual coordinates or device location today)
- Partner inventory calendar/blackout editing UI, property photos upload, partner payouts; settlement records not generated automatically
- Accommodation payments (only nursing visit payments are wired)
- Hospital merge workflow; admin hospital editing UI (API create only)
- Email/WhatsApp channels; regional-language templates (schema supports `language`)
- Reschedule is compensating, not single-transaction
- Favorites, caregiver-management UI, nurse earnings settlement view, reports export
- OpenAPI spec generation; Playwright E2E in CI (current e2e is a node HTTP script run manually)
- Recurring appointments are created as independent visits grouped by `recurrenceGroupId`; no series-level edit
