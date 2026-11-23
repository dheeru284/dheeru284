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

## Run 2026-11-23 — no applications submitted

Network: WebSearch and the lever.co and job-boards.greenhouse.io pages loaded. These were blocked (DNS/proxy): remotive.com, boards-api.greenhouse.io, canonical.com, echojobs.io, jobs.dcg.co. The headless browser reached Greenhouse once, then the tunnel failed. None of the roles below had a disclosed salary of ₹42L/yr or more, so nothing was auto-submitted.

| Company | Role | Remote eligibility | Salary | Match | Job URL | Status | Notes |
|---|---|---|---|---|---|---|---|
| YipitData | Senior Data Engineer – Global Team (India) | India remote (verified on posting) | Not stated ("competitive"); form asks for minimum yearly salary in INR | 85% | https://job-boards.greenhouse.io/yipitdata/jobs/7064418 | REVIEW | Needs 6+ yrs Spark/PySpark, SQL, Databricks/Delta; Airflow/dbt/Snowflake are nice-to-haves. Mostly IST hours, with US overlap 1–2 days/week. Required questions need your answers: an employment-gap explanation (resume ends Jan '26), minimum INR salary (suggest ≥ ₹42L), notice/start date, people-management detail, reference-call acknowledgment. |
| Resilinc | Senior Data Engineer | India, company fully remote | Not stated | 80% | https://jobs.lever.co/resilinc/98e013c3-84ff-4596-8712-6401c0fb3d55 (also .../db05e6d3-6024-420d-a8da-da6edfe3e821) | REVIEW | Stack: Databricks, Spark, Delta, Azure, Python/SQL, CI/CD. ClickHouse is not on your resume. Salary unknown, so it can't be confirmed ≥ ₹42L. |
| Dynatron Software | Sr. Analytics Engineer – Remote India | India remote (listing) | Not stated | 70% | https://portfoliojobs.llrpartners.com/companies/dynatron-software-2/jobs/85592600-sr-analytics-engineer-remote-india | REVIEW (unverified) | dbt-heavy role on Snowflake/Databricks. Posted Jul 2026, may be stale. |
| Sardine | Analytics Engineer | India remote (listing) | INR 34–50L/yr + equity | 70% | https://jobs.dcg.co/companies/sardine/jobs/65884289-analytics-engineer | BORDERLINE | Minimum ₹34L is below ₹42L; the range overlaps. Posting is over 6 months old. Site blocked here. |
| Opvia | Senior Analytics Engineer | India remote | ₹15–25L | — | wellfound.com/jobs/4521077 | REJECT | Below threshold |
| Weekday (clients) | Senior Data Engineer / Databricks / Fabric | India remote | ₹11–50L, ₹20–40L, ₹15–30L | — | apply.workable.com/weekday-1 | REJECT | Below threshold (min) |
| Onehouse | Sr SWE, Distributed Data Systems (IN) | India remote | Not shown | <60% | jobs.lever.co/Onehouse/3531e786-... | REJECT | Java/C++ systems role, skill mismatch |
| Karat | Senior Data Engineer (India) | Bangalore-only | — | — | job-boards.greenhouse.io/karat/jobs/8880766002 | REJECT | No longer on the board (likely closed) |
| Canonical | IoT / Junior Data Engineer | EMEA only | — | — | greenhouse canonical | REJECT | India not eligible / junior |
| Canonical | SWE – Data Infrastructure – Kafka | Worldwide | — | <60% | job-boards.greenhouse.io/canonical/jobs/5218601 | REJECT | Kafka/infra-ops focus not on resume |
| Databricks | Sr. Big Data Engineer (India remote) | India | — | — | various mirrors | REJECT | Mirrors say closed; customer-facing PS role; couldn't verify |
| Mutt Data, Care Access | (from Oct run) | — | — | — | — | REJECT | Already rejected 2026-10-07 (duplicate) |
