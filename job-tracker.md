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

## Run 2026-11-12 — 0 applications submitted, 7 REVIEW

Method: scanned ~380 employer boards directly (Greenhouse HTML, Lever HTML, Ashby public GraphQL) plus web search. Reachable: job-boards.greenhouse.io, jobs.lever.co, jobs.ashbyhq.com, wellfound.com, jobs.smartrecruiters.com. Blocked by proxy: job-boards.eu.greenhouse.io, apply.workable.com, remotive, weworkremotely, himalayas, in.indeed.com, weekday.works, databricks.com; LinkedIn guest API rate-limited (429).

Why nothing was applied: none of the India-eligible roles states a salary, so the ₹42 LPA minimum can't be confirmed (rule 1: do not invent salaries). Every match below is REVIEW. FX assumption for reference: about ₹88/USD (not a live rate).

| Company | Role | Remote eligibility | Salary | Match | Job URL | Status | Notes |
|---|---|---|---|---:|---|---|---|
| YipitData | Senior Data Engineer – Global Team (India) | India Remote (confirmed) | not stated | 88% | https://job-boards.greenhouse.io/yipitdata/jobs/7064418 | REVIEW (salary) | PySpark/Databricks/Delta/SQL, 6+ yrs; first hire, could lead the team; 1–2 days/week US overlap. Best fit found. Updated 2026-11-11. |
| Jobgether (partner undisclosed) | Senior Data Engineer – Data Platform | India; "worldwide remote"; contract | not stated | 85% | https://jobs.lever.co/jobgether/3f3a1375-5947-4c51-bf98-b41a7a0650ff | REVIEW (salary, contractor, intermediary) | Azure + Databricks + dbt Core + PySpark + Data Vault 2.0, 5+ yrs. Stack fits closely; no Data Vault on resume. |
| Resilinc | Senior Data Engineer | India, Full-time, Remote | not stated | 80% | https://jobs.lever.co/resilinc/98e013c3-84ff-4596-8712-6401c0fb3d55 | REVIEW (salary) | Databricks, Delta, Azure data services, ClickHouse, Python; customer-facing; 5+ yrs. |
| Paxos | Data Platform Engineer | Remote – India (confirmed) | not stated | 68% | https://jobs.ashbyhq.com/paxos/f8cbcedf-5b3a-463c-82d1-0d80b9c34e42 | REVIEW (salary, skills) | Fintech/regulated; Snowflake/Kafka/K8s/AWS/Terraform/Dagster stack. They say Spark background is welcome. Resume lacks Kafka/K8s/Terraform. Apply only via paxos.com/careers. |
| G-P (Globalization Partners) | Software Architect – Data Platform | India (Remote-First) | not stated | 72% | https://job-boards.greenhouse.io/globalizationpartners/jobs/7985150003 | REVIEW (salary, architect scope) | Databricks-native target architecture, PySpark/SQL hands-on PoCs. |
| Level Access | Senior Analytics Engineer | Remote; non-US/CA candidates considered, India not named | US $92–100k (≈₹81–88 L/yr); non-US pay "reviewed during interview" | 70% | https://job-boards.greenhouse.io/levelaccess/jobs/8859581002 | REVIEW (India eligibility, pay outside US) | dbt on Databricks, Unity Catalog, Power BI; wants 3+ yrs dbt and GTM/revenue data. |
| Karat | Senior Data Engineer (India) | Remote, Bengaluru residents only (you qualify) | not stated | 65% | https://job-boards.greenhouse.io/karat/jobs/8880766002 | REVIEW (salary, skills) | Python, Airflow, Postgres/Redshift, Terraform, Docker, AWS: weaker fit with an Azure-heavy resume. |
| Smart Working Solutions | Senior Data Engineer / Developer [HR221] | India, Remote, Full-time | not stated | 62% | https://jobs.lever.co/smart-working-solutions/d3ffbb13-01ad-4a06-8029-db5d911e71c4 | REVIEW (salary; likely below floor) | Azure SQL/T-SQL, Power BI, HubSpot/Xero/Stripe; 25% backend/API dev; CFO-facing. |

Rejected this run:
- Supabase – FinOps Data Engineer (Remote Global): needs deep AWS+GCP FinOps, BigQuery, Terraform. Major skill mismatch.
- Prefect – Senior Analytics Engineer: GTM/Salesforce/Omni focus, region unclear. Mismatch.
- Jobgether – Senior Architect Databricks (India, contract): needs 6+ yrs hands-on Databricks plus pre-sales leadership. Overreach.
- Jobgether – Lead DE 4C and Sr DE 4B (India): both require several Databricks/Azure certifications that the resume doesn't list.
- StarTree – Senior SWE, Data Platform (India Remote): Java/distributed-systems software role, not data engineering.
- Lightdash – Analytics Engineering Advocate: Europe only.
- GitLab Intermediate DE (Bangalore, below seniority); HackerRank Lead DE (hybrid Bangalore); Smartsheet Staff Eng Databricks (on-site Bangalore): not remote, or junior.
- Canonical data-infra roles (EMEA only); Twilio, Discord, Reddit, Affirm, Care Access (US/Canada/EU only); Mutt Data (LatAm only); OKX Data Engineering Director (too senior).
- Improving – Lead DE (Cutshort, ₹10–35 L), Two95 (₹12–24 L), C5i (₹27–36 L): below ₹42 L.
- Earlier-run items: Climb AI (Ashby board now shows no data roles), Billigence/EXL (sites still blocked; no new evidence).
