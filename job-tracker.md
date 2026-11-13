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

## Run 2026-11-13 — 0 applications submitted, 1 to review

Access: direct HTTP (curl/Playwright) to every job board is blocked by the egress proxy. The WebFetch tool could reach jobs.lever.co and job-boards.greenhouse.io. remotive.com, LLR portfolio boards and boards-api.greenhouse.io did not resolve. Application forms can't be submitted from this session, and no role found today publishes a salary at or above ₹42L/yr.

| Company | Role | Remote eligibility | Salary | Match | URL | Status | Notes |
|---|---|---|---|---|---|---|---|
| Resilinc | Senior Data Engineer | India, Remote (fully remote co.) | Not stated | ~85% | https://jobs.lever.co/resilinc/98e013c3-84ff-4596-8712-6401c0fb3d55 | REVIEW | Open 2026-11-13. 5+ yrs; Databricks/Spark/Delta, Python/SQL, Azure preferred, CI/CD. Gaps: ClickHouse, Terraform (nice-to-have). Salary unknown, so ₹42L can't be verified. Ask the recruiter for the band before applying. |
| Onehouse | Senior Software Engineer, Distributed Data Systems (IN) | India-Remote | Not visible (equity eligible) | ~50% | https://jobs.lever.co/Onehouse/3531e786-ad84-4d0d-a0bd-113415bd328f | REJECT | Core requirement is Java/C++ systems coding; resume doesn't support that. |
| YipitData | Sr. Backend Engineer (Infra / Data Feeds) | India, fully remote | Not stated (asks min INR) | ~45% | https://job-boards.greenhouse.io/yipitdata/jobs/7791555 | REJECT | Backend SWE, 10+ yrs, Kafka/Go/K8s. Skill mismatch. |
| YipitData | Senior Data Engineer / Pipeline / Platform (India Remote) | India | — | — | greenhouse 7179707, 7064588, 6703545 | REJECT | Expired (redirects to board) |
| Resilinc | Staff Data Engineer – AI Solutions; Senior DE db05e6d3 | India | — | — | lever | REJECT | Expired (404) |
| Jobgether | Senior Data Engineer (Team Lead), Senior DE 0f35f05e | India | — | — | lever | REJECT | Expired (404) |
| Jobgether (partner) | Senior Data Engineer, 6+ yrs | India remote | ₹1–2L/month | — | lever (search snippet) | REJECT | Below ₹3.5L/month |
| Globalization Partners | Sr. Data Engineer / Staff DE (India Remote-First) | India | — | — | greenhouse 6330426003, 7491812003, 7692014003 | REJECT | Expired (redirect to board) |
| dbt Labs | India data roles | — | — | — | greenhouse 4661362005 | REJECT | Expired (404) |
| Acryl Data | Data Platform Engineer | Bengaluru | — | — | greenhouse 5057616007 | REJECT | Expired; board has only DevOps role |
| Karat | Senior Data Engineer (India) | Remote, Bangalore only | — | — | aggregator | REVIEW (unverified) | Couldn't open employer page |
| MediaRadar, Billigence, BrightClaim, Dynatron (Sr Analytics Eng), Opvia, Tala, phData, Level Access | Senior DE / Analytics Eng (India remote) | India (per snippets) | Not stated | — | remotive / builtin / aggregators | REVIEW (unverified) | Hosts blocked; no salary published |
| CyberCoders, Livefront | Senior DE (Databricks) | US only | $142–190k / $150–180k | — | aggregators | REJECT | India not eligible |

Benchmarks seen: senior DE roles for foreign employers hiring in India typically quote ₹30–50L CTC. Many India-remote listings won't clear ₹42L unless they're paid in USD.
