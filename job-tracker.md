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

## Run 2026-11-15: no applications submitted

Why nothing was submitted: none of the India-eligible roles below publishes a salary, so none could be confirmed to meet the ₹42 LPA floor. YipitData's form also needs a minimum expected salary in INR, which needs your decision. This session can't fill in browser forms either: the job APIs (Greenhouse/Lever/Ashby, LinkedIn guest search) are blocked or were refused, and only posting pages could be read through web fetch.

| Company | Role | Remote eligibility | Salary | Match | Status | Job URL | Notes |
|---|---|---|---|---|---|---|---|
| YipitData | Senior Data Engineer – Global Team (India) | India Remote (stated) | Not listed ("competitive"); form asks minimum INR salary | 85% | REVIEW | https://job-boards.greenhouse.io/yipitdata/jobs/7064418 | Open. 6+ yrs; Spark/PySpark/SQL/Delta/Databricks required; Airflow/dbt/Snowflake nice-to-have. IST hours after onboarding, 1–2 days/week US overlap. First hire on a new team. Needs your salary figure and notice period. Best fit found. |
| Resilinc | Senior Data Engineer | India, fully remote | Not listed | 78% | REVIEW | https://jobs.lever.co/resilinc/98e013c3-84ff-4596-8712-6401c0fb3d55 | Open. 5+ yrs; Databricks/Spark/Delta, Azure preferred, ClickHouse (not on resume), CI/CD. Salary unknown; may be under ₹42L. |
| Jobgether (unnamed client) | Senior Architect – Data Engineering (Databricks) | Remote within India | Not listed | 65% | REVIEW | https://jobs.lever.co/jobgether/773c489b-9e9e-4922-bf7e-b6e7f062e30d | Contract. 10+ yrs, 6+ yrs hands-on Databricks (resume shows about 5.5 yrs, since Apr '20); Iceberg, DLT, Unity Catalog, containers. Intermediary. |
| Jobgether (unnamed client) | Lead Data Engineer 4C | India, fully remote | Not listed | 60% | REVIEW (weak) | https://jobs.lever.co/jobgether/30c730a8-e2f0-4c77-b7eb-a661ec58707f | Kafka/Airflow/AWS/Terraform required, which the resume doesn't support. |
| Rearc | Senior Data Engineer (India) | India (Pune; remote-eligible per search snippet) | Not seen | ? | REVIEW | https://jobs.ashbyhq.com/rearc/180396cb-92a2-4f78-b38b-748eb4341e12 | Ashby page didn't render; details unverified. Client-facing Databricks role. |
| Alimentiv | Senior/Lead Data Engineer (India) | Bangalore, remote | ₹20.95–36.04 L/yr | 85% | REJECT | https://jobs.lever.co/alimentiv-2/fcc7752c-a1ee-43f1-a419-e01ca24284a6 | Below salary floor (max ₹36L). |
| Jobgether (unnamed client) | Senior Data Engineer – Data Platform | India / "worldwide remote" | Not listed | — | REJECT | https://jobs.lever.co/jobgether/3f3a1375-5947-4c51-bf98-b41a7a0650ff | Requires fluent German and Data Vault 2.0. |
| Jobgether | Data Engineer – Global Team | India remote | — | — | REJECT | https://jobs.lever.co/jobgether/26017845-206b-4fad-a477-e6d1e5ea48e7 | Expired (404). |
| Oportun | Senior Data Engineer (R14287) | Remote – India | — | — | REJECT | https://job-boards.greenhouse.io/oportun/jobs/4740187005 | Link goes to the general board, so the posting is likely closed. |

Market note: India-remote senior Databricks roles found this run list ₹18–45 LPA where pay is shown. Glassdoor's Sr DE India median is about ₹21.75L. USD-paying worldwide-remote roles open to India were not found this run.
