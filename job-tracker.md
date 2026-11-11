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

## Run 2026-11-11 — no applications submitted

Why none were submitted: every role I confirmed as open and remote-from-India had no posted salary, so the ₹42 lakh/yr floor couldn't be checked. Under the routine's rules that makes them REVIEW, not APPLY. The open forms also ask for a minimum salary expectation and a notice period, and neither is in the resume.
FX assumption: about ₹95 per USD (mid-2026 sources; no dated November rate found). Floor ≈ $44k/yr.
Access this run: greenhouse.io and lever.co reachable. crossover.com, remotive, remoteok, himalayas, indeed and the Greenhouse/Lever JSON APIs blocked by the session network policy.

### REVIEW (verified open on the employer's ATS, India-remote, salary not stated)
| Company | Role | Remote eligibility | Salary | Match | Job URL | Date found | Notes |
|---|---|---|---|---|---|---|---|
| Resilinc | Senior Data Engineer | India, full-time remote | Not stated | ~85% | https://jobs.lever.co/resilinc/98e013c3-84ff-4596-8712-6401c0fb3d55 | 2026-11-11 | Databricks, Spark, Delta Lake, Azure (preferred), Python/SQL, 5+ yrs: strong fit. ClickHouse and customer-facing/FDE work are gaps. Best fit found. |
| OpenTable (Booking Holdings) | Senior Data Engineer (AI/ML) | "100% remote across India" | Not stated (form asks for minimum base expectation) | ~65% | https://job-boards.greenhouse.io/opentable/jobs/8817801002 | 2026-11-11 | Databricks/Spark/Snowflake match, but LLM/RAG/vector DB experience is *required* and isn't in the resume. Form also asks notice period (wants ≤30 days). |
| IDT Corporation | Senior Data Engineer (with AI/ML experience) | Remote, "only accepting applicants from India" | Not stated; B2B ($, gross) or FTE | ~60% | https://jobs.lever.co/idt/5156a826-424f-46da-aa38-e86aec3b36aa | 2026-11-11 | Snowflake/Redshift, Spark, Python fit. Requires 1–2 yrs hands-on AI/ML/RAG and Kafka, neither in the resume. Pay in USD may clear the floor. |
| Canonical | Python & Kubernetes Software Engineer – Data, Workflows, AI/ML & Analytics | Home based – Worldwide | Not stated (location-based) | ~55% | https://job-boards.greenhouse.io/canonical/jobs/5703396 | 2026-11-11 | Software-engineering role (Kubernetes, Kubeflow, Airflow, dbt). Kubernetes not in resume. Canonical has a long application questionnaire. |

### Leads that could not be verified this run
- Crossover / IgniteTech — Lead Data Engineer, listed at **$60k/yr (~₹57 lakh/yr, ~₹4.75 lakh/mo)**, any country, full-time remote. crossover.com is blocked here. This is the only lead with a stated salary above the floor. Worth checking manually: https://www.crossover.com/job-roles/finance/t-a0sIj000001G9h0IAC/ignitetech-lead-data-engineer
- Billigence — Senior Data Engineer (Azure Databricks), India remote contract (Built In listing ~23 days old). Still REVIEW from the last run; employer page not reached.
- Dynatron Software — Sr. Analytics Engineer, Remote India (dbt + Snowflake/Databricks), posted Jul 2026. Not verified.
- Outreach — Senior Analytics Engineer, remote within India (Snowflake, dbt, Airflow). Techstars board blocked.

### REJECT
- Nearform Senior Data Engineer, India (both permanent and contract) — postings closed.
- Oportun R14287, Level Access, XO Health, Proton.ai (now LATAM/Europe only) — postings closed or India removed.
- Jobgether India DE postings (4) and the earlier Resilinc Staff DE – AI Solutions — 404, closed.
- G-P Staff Data Engineer — closed.
- YipitData Senior Data Engineer (India) — no longer on their board.
- HackerRank Lead Data Engineer — hybrid, Bangalore office 3 days/week.
- OKX Data Engineering Director, APAC — Hong Kong work-right priority; director level.
- Weekday, Pitchnhire, EazyML, Opvia India roles — posted ranges ₹15–40 lakh, below the floor.
- GitLab Intermediate Data Engineer (Bangalore) — mid-level, office location.
