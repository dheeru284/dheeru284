# API v1

Base `/api/v1`. JSON. Success: `{ "data": ... }`. Error: `{ "error": { "code", "message", "details" } }` with codes `VALIDATION 400, UNAUTHENTICATED 401, FORBIDDEN 403, NOT_FOUND 404, CONFLICT 409, PRECONDITION_FAILED 412, COMPLIANCE_BLOCKED 451, RATE_LIMITED 429, PROVIDER_UNAVAILABLE 503`.
Auth: httpOnly `hn_session` cookie (SameSite=Lax) + Origin check on mutations. Pagination: `?limit=&offset=`.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | /auth/otp/request | public (rate-limited) | send OTP |
| POST | /auth/otp/verify | public | verify, create session; `registerAs` PATIENT/NURSE/ACCOMMODATION_PARTNER |
| POST | /auth/logout · GET /auth/me | signed in | |
| GET/POST | /patients | patient.self | profiles (consent required) |
| GET/POST | /patients/addresses | signed in | |
| POST | /caregivers | patient.self | link a caregiver |
| GET | /services | public | bookable catalog |
| POST | /matching | signed in | `{serviceId,addressId,date,time,genderPreference?,languages?,requestExpandedLimit?}` |
| GET/POST | /appointments | patient.self / appointment.book | list / create (optional `recurrence`) |
| GET | /appointments/:id | participant | role-filtered view |
| POST | /appointments/:id/transition · /reschedule · /review | role-checked | |
| POST | /visits/:id/checklist · /notes | visit.record | |
| GET/PUT | /nurses/me · PUT /nurses/me/availability · POST /nurses/me/{registrations,eligibility,submit} · GET /nurses/me/appointments | nurse.self | |
| POST | /nurse-credentials/uploads | nurse.self | returns signed private upload URL |
| GET/POST | /hospitals | public / hospital.manage | |
| GET | /accommodations/search · /accommodations/:id | public | |
| GET/POST | /accommodation-bookings · POST /:id/{cancel,extend,respond} | accommodation.book / stay.partner | |
| GET/PUT | /partners/me · GET /partners/me/bookings · POST /partners/me/properties | partner.self | |
| POST | /payments/orders · /payments/confirm · /payments/webhook (signed) · /refunds | | |
| GET | /notifications | signed in | |
| POST | /support | support.write | ticket / complaint / incident |
| GET/POST | /privacy (`?export=1`) | privacy.self | |
| * | /admin/{settings,flags,nurses,nurses/:id/status,nurses/:id/eligibility,credentials/:kind/:id,qualifications/:id,services,properties,complaints,audit,metrics,privacy} | admin perms | |
| GET/POST/PATCH | /compliance | compliance.manage | |
| GET | /health | public | DB liveness |

An OpenAPI document is not yet generated (known gap); Zod schemas in each route are the contract.
