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

## Run 2026-11-28 — 0 applications submitted

**Why nothing was submitted:** the session can't send applications. Shell/browser network access to greenhouse.io, lever.co, ashbyhq.com and most job boards is blocked, and a LinkedIn scrape was refused. Lever and Greenhouse pages could only be *read* through the fetch tool. Every qualifying role also has at least one blocker that needs your input: no published salary, a required "minimum salary (INR)" field, notice period, LinkedIn URL, or an explanation of the gap since Jan '26. Unreachable hosts this run: remotive.com, builtin.com, lumenalta.com, phdata.io, jobs.dcg.co, portfoliojobs.llrpartners.com, in.linkedin.com, and api.lever.co / boards-api.greenhouse.io (shell).

FX used for conversion: about ₹84/USD (approximate, live rate not fetchable). Threshold: ₹42 L/yr, ₹3.5 L/month.

### REVIEW — strongest first (all verified open on the employer page unless noted)

| # | Company | Role | Remote eligibility | Salary | INR/yr | Match | Job / Apply URL | Notes / blocker |
|---|---|---|---|---|---|---|---|---|
| 1 | YipitData | Senior Data Engineer – Global Team (India) | India Remote (explicit) | Not published | ? | 88% | https://job-boards.greenhouse.io/yipitdata/jobs/7064418 | Core stack is exactly yours: Spark/PySpark/SQL/Delta/Databricks, 6+ yrs; dbt/Snowflake nice-to-have. Form requires: **minimum yearly salary in INR**, notice period, **employment gaps** (Jan '26 onward), people-management experience, LinkedIn URL, reference-call acknowledgment. Suggest entering ≥ ₹42 L. Needs 1–2 days/week US-hours overlap. |
| 2 | Sardine | Analytics Engineer | India – Remote | INR 3,400k–5,000k + equity | ₹34–50 L | 72% | via jobs.dcg.co/companies/sardine/jobs/65884289 (unreachable) | BORDERLINE: minimum ₹34 L is below ₹42 L, maximum is above. Listing is 6+ months old; open status unverified. Fintech/fraud analytics, dbt-style work. |
| 3 | IDT | Senior Data Engineer (with AI/ML experience), India | Remote, "only accepting applicants from INDIA" | "Competitive"; B2B or FTE | ? | 65% | https://jobs.lever.co/idt/5156a826-424f-46da-aa38-e86aec3b36aa | Spark/Python/SQL/Snowflake fit. Gaps: Kafka, vector DBs/RAG/LLM frameworks (1–2 yrs AI/ML hands-on required; your resume shows ML coursework and predictive modelling only). Salary unknown. |
| 4 | JumpCloud | Staff Data Engineer, India | Remote India; must be located and authorised in India | Not published | ? | 58% | https://jobs.lever.co/jumpcloud/60f9796e-9f63-416e-8c7b-8e16cd2ee3dc | 10–12 yrs and SQL/Python/warehouse/ELT fit, but **Golang is listed as must-have** and Kafka/Airflow are core. Not on your resume. Apply only if you have Go experience. |
| 5 | Dynatron Software | Sr. Analytics Engineer – Remote India | Remote India (likely independent contractor) | Not published | ? | 75% | via LLR Partners portfolio page (unreachable) | dbt + Snowflake/Databricks, 6–8+ yrs, SQL/Python. Contractor structure and open status unverified. |
| 6 | Rearc | Senior Data Engineer (India) | India / telecommute (from search snippet) | Not published | ? | ? | https://jobs.ashbyhq.com/rearc/180396cb-92a2-4f78-b38b-748eb4341e12 | Ashby page is JS-rendered; details not readable. Rearc is AWS-heavy. Unverified. |
| 7 | Outmarket AI | Senior Data Engineer | US/India remote (from search snippet) | Not published | ? | ? | https://jobs.ashbyhq.com/outmarket/f1ad2211-ad8e-4c7d-8fd3-350904f24e2c | Posted Jun 2026; details unreadable. Unverified. |
| 8 | Canonical | Python & Kubernetes Software Engineer – Data, Workflows, AI/ML & Analytics | Home based – Worldwide | Not published | ? | 50% | https://job-boards.greenhouse.io/canonical/jobs/5703396 | Worldwide is genuine, but the role is Linux/K8s/charm-operator software engineering more than data engineering. Travel 2×/yr. Weak fit. |

### REJECT
- JumpCloud — Senior Manager, Data Engineering (India): needs 8+ yrs applied ML and managing 8+ people (ML engineers). Mismatch.
- Canonical — Engineering Manager, Data Platform / MLOps & Analytics: manager roles; no people-management track record on resume. Software Engineer – Data Infrastructure (Kafka/OpenSearch): EMEA only.
- Alimentiv — Senior Data Engineer (India), Lever: posting closed (404).
- HighLevel — Lead Data Engineer, Lever: posting closed (404).
- Jobgether Lever postings (ad30c647, 4d426592, e40d8356, 452abe0e, 0f35f05e): all closed (404).
- Excelon Solutions — Senior Azure DE, remote: ₹40–45 L, minimum below threshold, and posting about 1 yr old.
- Data PlatformExperts (₹15–25 L), Doodleblue (≤₹1.5 L/month), Wellfound Senior Analytics Engineer (₹15–25 L): below threshold.
- Kiash Solutions (Hyderabad on-site), Enqora (hybrid): not remote.
- Livefront ($150–180k), Indeed Lead Data Engineer – Databricks ($175–230k), Mux, Machinify, Shield AI, Aya Healthcare, Attentive: US only. G-P Senior DE Data Platform: Poland only. BairesDev Databricks: LatAm.
- Previously tracked Billigence, Climb AI, EXL: not re-verifiable this run (hosts blocked); still REVIEW from 2026-10-07.
