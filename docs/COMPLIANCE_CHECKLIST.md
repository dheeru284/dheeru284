# Compliance & operational safety checklist

This is not legal advice. Have a qualified advisor confirm the items marked ⚖ for your actual recipient jurisdictions.

## Before any live outreach
- [ ] ⚖ Lawful basis recorded per recipient region. For B2B cold email, legitimate interest is commonly relied on in the UK/EU; India's DPDP Act 2023 and its Rules; UAE PDPL (Federal Decree-Law 45/2021) with DIFC/ADGM rules where the recipient is in those free zones; US CAN-SPAM.
- [ ] ⚖ Business postal address in the signature, which CAN-SPAM requires. Fill it in Onboarding.
- [ ] Every message identifies EpohTech and offers a working opt-out. The template enforces this, and a `List-Unsubscribe` header is set.
- [ ] Opt-out honoured immediately and permanently. Covered by the `suppressions` table and test 08.
- [ ] Only business contact data from public or authorized sources is stored, each item with `source_url`.
- [ ] No personal email addresses. Review imported contacts.
- [ ] Sender domain has SPF, DKIM and DMARC set up, and volume starts low. Defaults are 5/hour and 25/day.
- [ ] One sending account only. Never rotate accounts to get around limits.

## Platform terms
- [ ] LinkedIn: no scraping, no browser automation, no automated connection requests or messages. Manual send only unless a partner agreement exists (test 16).
- [ ] Job boards and freelance platforms: apply only through the platform's own method and only after human authorization (`remote.authorize_application`).
- [ ] Apollo and other data vendors: use within the licence. Do not re-export.

## Content honesty
- [ ] Profile contains only verified facts, certifications and case studies.
- [ ] No invented rates, budgets, durations or client names. Compensation is recorded only when published.
- [ ] Inferred signals appear as "[Inference]" and are never cited in messages.

## Operations
- [ ] Emergency stop tested in your deployment (Settings → EMERGENCY STOP).
- [ ] Audit log reviewed weekly. Filter: warnings/errors.
- [ ] Dead-letter jobs reviewed (Settings → Job queue, `DEAD`).
- [ ] Backups scheduled and one restore tested.
- [ ] Secrets only in env or a secret manager. `.env` stays out of git, tokens are encrypted, logs are redacted (test 14).
- [ ] Admin password at least 12 characters. The app sits behind TLS. Remove `ADMIN_PASSWORD` from env after the first run.
- [ ] Data deletion requests: delete the organization (contacts and evidence cascade) but keep the suppression row.
