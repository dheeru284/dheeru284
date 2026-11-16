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

## Run 2026-11-16 — no applications submitted

Blocker: the network block is back. greenhouse.io, lever.co, ashbyhq.com, remoteok, himalayas, remotive and the FX API all fail (CONNECT 403 / DNS not allowed), and linkedin.com returns 403. No posting could be opened, verified or applied to. The leads below come only from search snippets. INR figures assume about ₹88/USD because no live rate could be fetched.

| Company | Role | Remote eligibility (snippet) | Salary | INR/yr (est.) | Match | Source / URL | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| G-P (Globalization Partners) | Senior Software Engineer (Data Platform) | India (Remote-First) | not listed | ? | ~85% | job-boards.greenhouse.io/globalizationpartners/jobs/7698156003 | REVIEW (top lead) | Databricks Lakehouse, Spark, Delta/DLT, perf tuning: strong fit. 5+ yrs. Salary needed. |
| YipitData | Senior Data Engineer / Senior Data Pipeline Engineer, Global Team (India) | India remote | "competitive", not listed | ? | ~80% | job-boards.greenhouse.io/yipitdata/jobs/7064418 (also /yipitdatajobs/jobs/7179707) | REVIEW | Databricks + Spark tuning. Hours are 11am–8pm IST (2–11pm IST during onboarding). Check which ID is still live. |
| phData | Senior Data Engineer (India) | India remote, IST hours | not listed | ? | ~75% | workingnomads.com/jobs/senior-data-engineer-phdata-1653192 | REVIEW | Snowflake/Databricks/dbt consulting. Historically pays near Indian market rates, so the salary threshold is doubtful. |
| AgileEngine | Senior Data Engineer (Databricks, PySpark) | Remote India | not listed | ? | ~80% | via remote board (posted 2026-11-11) | REVIEW | New posting. Find it on agileengine.com. |
| OneSignal | Senior Data Engineer | "Remote (Global)" | $170–190k | ₹1.50–1.67 Cr | ~65% | snippet, dated 2026-06-04 | REVIEW | Salary clears the floor easily. India eligibility unverified and the posting may be stale. |
| Fetch | Senior Data Engineer | "Remote (Global)" | $149.5–206.6k | ₹1.32–1.82 Cr | ~65% | snippet, dated 2026-06-30 | REVIEW | Same caveats as OneSignal. |
| DATAMAXIS | Senior Data Engineer, Databricks/PySpark | India remote | not listed | ? | ~80% | remoterocketship.com (blocked) | REVIEW | Probably a contractor/staffing firm. |
| Object Edge | Senior Engineer, Data Engineering (Databricks) | India, contract | not listed | ? | ~75% | himalayas.app/companies/object-edge | REVIEW | Contract role. |
| Camunda | Senior Data Engineer | UK / US only | $143.8–231.9k | — | — | remotivated.com | REJECT | India not eligible. |
| Grafana Labs | Senior Data Engineer | USA only | $162–195k | — | — | remotive.com | REJECT | India not eligible. |
| Jobgether (partner) / Weekday / Qureos / NewVison | various Databricks/Snowflake roles | India | ₹12–30 LPA | — | — | various | REJECT | Below ₹42 LPA. |

Carried over from 2026-10-07 and still unverified: Billigence, Climb AI, EXL.
To unblock: add greenhouse.io, boards-api.greenhouse.io, lever.co, api.lever.co, ashbyhq.com, linkedin.com, remoterocketship.com and an FX API host to this environment's allowed network domains.
