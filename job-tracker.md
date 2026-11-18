# Job search tracker

## Run 2026-10-07 — no applications submitted

Blocker: this cloud session's egress proxy blocks job sites (lever.co, greenhouse.io, ashbyhq.com, remoterocketship.com, etc.), so no posting could be opened, verified (India eligibility, salary, still open) or applied to. Only web-search snippets were available. Nothing below is verified.

Resume facts used: ~10 yrs; Azure Databricks, Spark/PySpark, ADF, Synapse, Fabric, SQL, Python, dbt, Snowflake; no Kafka/Airflow/Terraform/AWS depth listed; last role Akamai Mar '22–Jan '26. Based in Bengaluru.

| Company | Role | Source | Status | Notes |
|---|---|---|---|---|
| Billigence | Senior Data Engineer (Azure Databricks), India – Remote | remoterocketship.com listing | REVIEW (unverified) | Strong stack match (Databricks, Delta, Synapse). Salary not seen. Check on employer site. |
| Mutt Data | Data Engineer Senior – Databricks | jobs.lever.co/muttdata/e3e183ff-ecf5-435a-a218-20f846007c8a | REVIEW (unverified) | "Work from anywhere" claim in snippet; India eligibility and salary unconfirmed. |
| Care Access | Senior Data Engineer | job-boards.greenhouse.io/careaccess/jobs/4112890009 | REVIEW (unverified) | 100% remote; Databricks/SQL/dbt/Python/Azure match. Country eligibility and salary unknown. |
| Climb AI | Senior Data Engineer | jobs.ashbyhq.com/climb-ai/3d29064b-fb8e-45c6-878f-b88313c6325e | REVIEW (unverified) | Databricks platform modernization; location rules unknown. |
| Jobgether | Data Engineer (Azure/Databricks) | jobs.lever.co/jobgether/b33f80b5-6d9b-4601-926d-f2fdaab84cfb | REVIEW (unverified) | Aggregator/intermediary; find the real employer. |
| Weekday (client) | Senior Data Engineer, Fabric + Databricks | Weekday | REJECT | Listed ₹20–40 lakh/yr; minimum is below ₹42 lakh. |
| External Global | Sr. Databricks Engineer | dreamworkhq.com | REJECT | USA-only remote, $106–140k, requires Databricks Pro cert. |

## UAE check 2026-10-07 — no remote-from-India roles found

Search snippets only (job sites are blocked, nothing opened or applied to). UAE roles found are on-site/hybrid in Dubai/Abu Dhabi, which needs relocation, so REJECT for remote-from-India:
- Cognizant — Senior Databricks Engineer (Dubai/Abu Dhabi)
- BigTapp/Claids — Senior Data Engineer, Azure Databricks, banking (Dubai); also needs banking domain experience
- IDC Technologies — Senior Azure Data Engineer, 7–10 yrs (UAE)
- Al-Futtaim Group — Data Engineer, Azure/Databricks (Dubai)
- Senior Data Engineer, Databricks/Fabric (Abu Dhabi, posted 7 Jul 2026)
Salary context: UAE data engineer averages about AED 12.7–13.4k/month, roughly ₹3.0–3.2 lakh at about ₹24/AED (assumed rate, not live). Your ₹3.5 lakh/month floor is about AED 14.5–15k, so many UAE roles would be borderline anyway.

## UAE ~AED 25k/month search 2026-10-07 — NOT applied (job sites blocked; user approval needed)

Unverified, from search snippets. Work mode matters: your earlier rule was fully remote or <=4 office days/month.

| Company | Role | Salary | Work mode | Source | Status |
|---|---|---|---|---|---|
| (unnamed) | Senior Data Engineer, Azure Data Platform & Analytics, Dubai | AED 28–38k/mo | unknown | freehire.me / GulfTalent-type listing | REVIEW — salary fits, mode unknown |
| (unnamed) | Lead Data Engineering – Platform Ops | AED 35–50k/mo | unknown | freehire.me | REVIEW — may exceed experience scope (lead/ops) |
| EXL | Lead Data Engineer – Azure + Fabric | not seen | unknown | dreamworkhq.com/job/d179aae1-986a-4f43-b161-210b717494bb | REVIEW — strong stack fit, 8+ yrs; location unclear |
| Eutopia Solutions | Data Engineering Lead (Dubai) | not seen | unknown | freehire.me | REVIEW |
| (unnamed) | Azure Data Engineer (Data Lake Ownership) | not seen | unknown | gulftalent.com/uae/jobs/azure-data-engineer-data-lake-ownership-602082 | REVIEW |
| Keyrock | Senior Data Engineer, Abu Dhabi | AED 15–23k/mo | unknown | search snippet | REJECT — min below target |
Some UAE Lead roles are hybrid 3 days office / 2 remote, which breaks the 4-days-per-month rule.

## Verification after network change 2026-10-07
- Mutt Data (Lever): open, but "Remote - Latam" only, India not allowed -> REJECT.
- Care Access (Greenhouse 4112890009): posting URL redirects to the company board (likely closed); board lists US/Poland/Brazil only, no India -> REJECT.
- Climb AI (Ashby): page is JavaScript-rendered, details not readable without a browser -> still REVIEW.
- Billigence, EXL: remoterocketship.com and dreamworkhq.com still blocked by proxy -> still REVIEW.
- Reachable now: lever.co, greenhouse.io, ashbyhq.com, linkedin.com. Still blocked/403: bayt.com, gulftalent.com, ae.indeed.com, naukri.com, remoterocketship.com, dreamworkhq.com.

## Run 2026-11-18 — no applications submitted

Blocker: shell/browser egress to job sites is blocked again (Greenhouse/Lever/Ashby APIs, himalayas.app, phdata.io, api.ashbyhq.com all refused). Read-only page fetches worked for job-boards.greenhouse.io and jobs.lever.co, so the top roles below were checked on the employer page. Nothing could be submitted.
FX used: about ₹94/USD (13 Nov 2026 quote). Your ₹42 lakh/yr floor is about $44.7k/yr.

| Company | Role | Remote eligibility | Salary | Match | Job/Apply URL | Status | Notes |
|---|---|---|---|---|---|---|---|
| YipitData | Senior Data Engineer - Global Team (India) | India Remote (verified on Greenhouse) | Not listed; form asks "minimum required yearly salary (INR)" | ~85% | https://job-boards.greenhouse.io/yipitdata/jobs/7064418 | REVIEW — ready to apply | 6+ yrs; Spark/PySpark/SQL/Delta/Databricks required; Airflow/dbt/Snowflake nice-to-have. US overlap during onboarding, then IST except 1–2 days/week. No work-auth question. Need your salary floor (e.g. ₹42L+) and notice period. |
| Resilinc | Senior Data Engineer | Remote (India) (verified on Lever) | Not listed | ~85% | https://jobs.lever.co/resilinc/98e013c3-84ff-4596-8712-6401c0fb3d55 | REVIEW — ready to apply | 5+ yrs; Databricks, Spark, Delta Lake, Python, SQL, Azure preferred; ClickHouse and customer-facing work. Salary unknown, so ₹42L floor not confirmed. |
| OpenTable (Booking Holdings) | Senior Data Engineer (AI/ML) | 100% remote across India (verified on Greenhouse) | Not listed; form asks minimum base salary | ~70% | https://job-boards.greenhouse.io/opentable/jobs/8817801002 | REVIEW | Databricks/Snowflake/Spark/Delta/Airflow fit. Also requires hands-on LLM/GenAI, RAG, vector DB work, which your resume does not show. Apply only if you have that experience. |
| Solvd | Senior Data Engineer (Azure Databricks) | Built In says hiring remotely in India | Not seen | ~85% | https://builtin.com/job/senior-data-engineer-azure-databricks/8779960 | REVIEW (unverified) | Databricks/PySpark/Delta/Synapse, medallion, fintech client. Employer page not found. |
| Billigence | Senior Data Engineer – Azure Databricks | India Remote (aggregators) | Unspecified; contract | ~85% | https://builtin.com/job/senior-data-engineer-azure-databricks/8738671 | REVIEW (unverified) | Carried over from the October run. Contract; Synapse → Databricks migration. |
| phData | Lead / Senior Data Engineer | India Remote (aggregators) | Unspecified | ~75% | phdata.io/jobs (blocked) | REVIEW (unverified) | 8+ yrs plus team lead experience; Snowflake/Databricks. Careers site blocked. |
| Foundever | Senior Data Engineer (Remote, Any Location, IN) | India (Himalayas listing, 2026-11-06) | Unknown | ? | himalayas.app (blocked) | REVIEW (unverified) | Databricks on Azure/AWS. Could not open it. |
| Inficare Technologies | Senior Databricks Data Engineer | USA only | $62/hr | — | remotive.com | REJECT | India not eligible. |
| Lumenalta | Databricks on Azure | US time zones only | CA$83–153k | — | — | REJECT | India not eligible. |
| Insight Global | Data Engineer - INTL India | India | $12–23/hr est. | — | insightglobal.com | REJECT | About ₹23–43L/yr; minimum below the floor. |
| Opvia / EazyML / Qureos roles | Senior DE / Analytics Engineer | India | ≤₹40L | — | — | REJECT | Below the salary floor. |
| Alimentiv, Jobgether (several) | Senior Data Engineer | India | — | — | jobs.lever.co | REJECT | Posting returns 404 (closed). |
