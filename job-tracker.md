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

## Run 2026-11-25 — no applications submitted

**Why nothing was submitted:** the session can't submit forms. Shell traffic (curl, Playwright) to job sites fails, and the web fetcher only resolves jobs.lever.co, job-boards.greenhouse.io and wellfound.com. remotive.com, builtin.com, boards-api.greenhouse.io and LLR portfolio pages don't resolve. Even with access, the best match needs answers that aren't in the resume (see below).

FX used: about ₹96.5/USD (latest dated quote found, Jul 2026; no live rate reachable). Your ₹42 L/yr floor ≈ USD 43.5k/yr.

| Company | Role | Remote eligibility | Salary | INR/yr | INR/mo | Match | Job URL | Source | Status | Date found | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| YipitData | Senior Data Engineer – Global Team (India) | India Remote (posting: "remote opportunity based in India") | Not on Greenhouse. Wellfound shows "$100k–$200k" | ~₹96 L–1.93 Cr if USD (unconfirmed) | ~₹8.0–16 L | 85% | https://job-boards.greenhouse.io/yipitdata/jobs/7064418 | Greenhouse (verified live), Wellfound 3338784 | REVIEW | 2026-11-25 | Stack fits closely: Spark/PySpark/SQL/Delta/Databricks, 6+ yrs, dbt/Snowflake nice-to-have. US overlap 1–2 days/wk. Required answers I can't give truthfully: min salary in INR, earliest start/notice, employment gap since Jan '26, people-management detail, LinkedIn URL, why looking. |
| Hackett Group | Senior Data Engineer – Remote, India | India remote | not seen | – | – | ~80% (Azure Databricks/PySpark) | https://builtin.com/job/senior-data-engineer-remote-india/10867147 | BuiltIn (blocked) | REVIEW (unverified) | 2026-11-25 | ~86 days old; salary unknown, Indian consultancy, likely below floor. |
| AgileEngine | Data Engineer (Python/PySpark/Databricks) | Remote India | not seen | – | – | ~70% (Airflow listed, not on resume) | freehire.me listing, posted 2026-11-11 | freehire.me | REVIEW (unverified) | 2026-11-25 | Salary unknown. |
| Dynatron Software | Sr. Analytics Engineer – Remote India | India remote | not seen | – | – | ~70% (deep dbt needed) | https://portfoliojobs.llrpartners.com/companies/dynatron-software-2/jobs/85592600-sr-analytics-engineer-remote-india | LLR portfolio board (blocked) | REVIEW (unverified) | 2026-11-25 | Posted Jul 2026, may be stale. |
| Remote.com | Senior Analytics Engineer (APAC priority) | Global/APAC | $42.75k–$102k | ₹41 L min | – | – | https://job-boards.greenhouse.io/remotecom/jobs/5748624003 | Greenhouse | REJECT | 2026-11-25 | Posting closed ("no current openings"); min was also just under floor. |
| Allshore Talent | Senior Data Engineer (contract) | Employer page: LATAM only | $23.75–25/hr, 35–40 h/wk | ₹41.7–50 L (estimate) | – | – | https://allshoretalent.recruitee.com/o/senior-data-engineer-100-remote-latam-only | Recruitee | REJECT | 2026-11-25 | India listed only by an aggregator; employer page says LATAM. |
| Opvia | Senior Analytics Engineer | India remote | ₹15–25 L | ₹15–25 L | – | – | https://wellfound.com/jobs/4521077-senior-analytics-engineer | Wellfound | REJECT | 2026-11-25 | Below salary floor. |
| Weekday (client) | Senior Databricks Engineer | Remote India | ₹15–30 L | – | – | – | jobgether.com offer 69c2a0170cd461dff7f6942c | Jobgether | REJECT | 2026-11-25 | Below salary floor. |
| GitLab | Intermediate Data Engineer | India | not seen | – | – | – | remotive listing 6539465 | Remotive (blocked) | REJECT | 2026-11-25 | Intermediate level, below your seniority. |
| Massive Rocket | Lead Data Engineer (contract) | "Worldwide" but needs an existing work visa | not seen | – | – | – | remotive listing 6410581 | Remotive | REJECT | 2026-11-25 | Visa required, no sponsorship. |
| Société Générale | Sr SE – Data Engineer (Databricks/PySpark) | Bangalore hybrid | – | – | – | – | careers.societegenerale.com 26000IB7 | Employer | REJECT | 2026-11-25 | Hybrid, not remote. |

Earlier REVIEW items still open (not re-verified, hosts blocked): Billigence (India – Remote, salary unknown), Climb AI, EXL, UAE leads.

**To unblock applications:** (1) allow these domains in the environment's network settings: job-boards.greenhouse.io, boards.greenhouse.io, jobs.lever.co, jobs.ashbyhq.com, remotive.com, builtin.com, wellfound.com, myworkdayjobs.com. Shell/Playwright access is needed for submitting, not just the web fetcher. (2) Add a short answers file to this repo with your LinkedIn URL, notice period/earliest start, minimum INR salary to quote (e.g. ₹42 L or higher), a one-line explanation of the gap since Jan 2026, people-management experience, and your reason for looking.
