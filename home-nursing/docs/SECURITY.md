# Security checklist

Implemented (with tests where noted):
- [x] OTP: 6 digits, HMAC-hashed at rest, 5-min expiry, 5 attempts, single-use under concurrency, per-phone and per-IP rate limits (tested)
- [x] Sessions: random 256-bit token, SHA-256 stored, httpOnly/Secure/SameSite=Lax cookie, expiry + revocation, suspended users rejected (tested)
- [x] RBAC enforced in API wrapper and domain services; resource-level checks (patient/caregiver/nurse/partner ownership) (tested)
- [x] CSRF: SameSite + Origin check on mutating requests
- [x] Input validation with Zod on every route; Prisma parameterised queries; React escaping
- [x] Security headers (HSTS, nosniff, frame DENY, referrer, permissions policy, CSP allow-listing Razorpay)
- [x] CSV exports neutralise formula injection (tested); exports audited
- [x] Prescription views and credential views audited; signed URLs expire in ≤5 min
- [x] Non-app notification templates reject clinical terms
- [x] Upload type/size allow-list; private-key storage, short-lived signed URLs; document views audited (tested)
- [x] Payments: server-side signature verification, signed webhooks, replay protection, idempotent capture (tested)
- [x] Logs redact OTP/token/secret/clinical fields (tested); SMS bodies contain no health details
- [x] Audit log for verification decisions, status changes, settings, flags, compliance, privacy actions, refunds
- [x] Production boot refuses mock providers, default secrets, exposed OTP (tested)

Not yet done — required before launch:
- [ ] Independent penetration test and code review
- [ ] Rate limits on remaining write endpoints; bot protection on OTP
- [ ] Field-level encryption for clinical notes; DB/storage encryption at rest via managed infra
- [ ] Break-glass clinical access workflow for admins
- [ ] Session listing/"sign out everywhere"; admin MFA
- [ ] Malware scanning of uploads; S3 bucket policy (block public access)
- [ ] Secrets in a manager (not .env); key rotation runbook
- [ ] Incident response plan aligned to CERT-In 6-hour reporting
