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

## Run 2026-11-20 — 0 applications submitted

Network: the sandbox can read jobs.lever.co and job-boards.greenhouse.io through web fetch. remotive.com, builtin.com, boards-api.greenhouse.io, databricks.com, brenxor.com and remoterocketship.com do not resolve, and direct curl is blocked entirely. No posting found today had a published salary that confirms ₹42L/yr, so nothing passed the APPLY bar.

| Company | Role | Location (verified) | Salary | INR/yr | Match | Job URL | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Resilinc | Senior Data Engineer | India, Remote (Lever, live 2026-11-20) | Not listed | ? | ~85% | https://jobs.lever.co/resilinc/98e013c3-84ff-4596-8712-6401c0fb3d55 | REVIEW — salary unknown | Databricks/Spark/Delta, Azure preferred, Python/SQL, ETL, CI/CD, 5+ yrs. Gaps: ClickHouse; Terraform/streaming are nice-to-haves. Best stack fit found. Ask recruiter for band before applying. |
| HighLevel (GoHighLevel) | Staff Engineer – Distributed Data Systems & Infrastructure | Remote — Employee India (Lever) | Not listed | ? | ~60% (est.) | https://jobs.lever.co/gohighlevel/30e5e3c1-c7e6-49fc-8598-2fd10b937ce0 | REVIEW — infra-heavy, JD not read | Platform/database infrastructure role; probably weaker fit than a pipeline role. |
| Globalization Partners (G-P) | Staff Data Engineer | India (Remote-First) per search snippet | Not listed | ? | ~65% | https://job-boards.greenhouse.io/globalizationpartners/jobs/6330426003 | REVIEW — could not confirm still open | Snippet says 12+ yrs needed; resume shows ~10. |
| Level Access | Senior Analytics Engineer | "Remote" (bands for US/CA; other countries "reviewed") | US$92–100k | ~₹78–85L (est. at ₹85/USD) | ~55% | https://job-boards.greenhouse.io/levelaccess/jobs/8859581002 | REVIEW (weak) | India eligibility not stated. Needs 3+ yrs dbt plus Salesforce/SaaS revenue-metrics domain, which the resume doesn't show. |
| Level Access | Senior Data Engineer (Remote – India) | — | — | — | — | job-boards.greenhouse.io/levelaccess/jobs/8498093002 | REJECT — no longer on board | |
| YipitData | Senior Data Engineer (Global Team – India) | — | — | — | — | job-boards.greenhouse.io/yipitdatajobs/jobs/7179707 | REJECT — closed (redirects to board) | Board still has India-remote Senior Software Engineer roles (not data). |
| Resilinc | Staff Data Engineer – AI Solutions | — | — | — | — | jobs.lever.co/resilinc/1ebc862c-… | REJECT — 404, closed | |
| Jobgether | Senior Data Engineer (several) | — | — | — | — | jobs.lever.co/jobgether/… | REJECT — 404, closed | |
| Mutt Data | Data Engineer Senior – Databricks (various) | LatAm/Argentina/Mexico | — | — | — | jobs.lever.co/muttdata | REJECT — India not eligible | Re-checked: all LatAm. |
| Jellyfish | Staff Data Engineer | Remote – US | — | — | — | — | REJECT — India not eligible | |
| Weekday clients / Data Hatch / Shivaay / NewVison | Senior (Databricks) Data Engineer | Remote India | ₹12–40L | ≤₹40L | — | — | REJECT — below ₹42L | |
| Databricks | Sr. Big Data Engineer (India remote) | — | aggregator *estimate* ₹25–35L | — | — | databricks.com (blocked) | REVIEW (unverified) | Careers site blocked; salary shown is an aggregator's estimate, not the employer's figure. |

Market note: every India-remote senior DE posting with a published salary this run was ₹12–40L. Roles above ₹42L almost always leave salary undisclosed, so for each one the recruiter has to confirm the band first.
