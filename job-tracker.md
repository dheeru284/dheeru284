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

## Run 2026-11-14 — 0 applications submitted, 9 for review

**Why nothing was submitted:** I can't log in to LinkedIn (no account in this session). Greenhouse forms that do load ask for things I can't fill in for you: a minimum salary, your notice period (your resume shows Akamai ended Jan '26, but your current status isn't stated), and a privacy-policy acknowledgement, which counts as agreeing to legal terms for you. Blocked hosts: remoterocketship, arc.dev, and the Greenhouse/Lever/Ashby JSON APIs. Reachable: LinkedIn public pages and Greenhouse/Lever/Ashby HTML pages.
**Coverage:** 814 LinkedIn postings (last 14 days, remote filter; 10 title variations; India/Worldwide/Asia), 314 detail pages parsed, plus searches of Greenhouse/Lever/Ashby.
**Salary filter:** ₹42 L/yr ≈ US$48k at about ₹88/USD (approximate rate, not live). Almost no India-remote posting states a salary, so only 2 could be tested against the threshold.

### REVIEW — India-remote, needs your decision
| # | Company | Role | Remote eligibility | Salary | INR/yr (min) | Match | Job URL | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | HSO India | Lead Data Engineer – Microsoft Fabric & Azure (LI 4486769329) | Remote / WFH, India | "Best in market" | unknown | 85% | https://www.linkedin.com/jobs/view/4486769329 | 10+ yrs; Fabric/ADF/Synapse/Databricks match your stack closely. Notice period immediate to 30 days. Posted ~Nov 10. |
| 2 | EazyML (via Weekday YC W21) | Lead Data Architect (Fabric) (LI 4488932724; duplicate 4488941299; EazyML direct 4490334404) | Remote, anywhere in India | ₹20–60 L/yr | ₹20 L (min below) | 85% | https://www.linkedin.com/jobs/view/4488932724 | BORDERLINE: the range overlaps ₹42 L but the minimum is below it. 8+ yrs, 2+ yrs Fabric, US-ET overlap. Posted Nov 13. |
| 3 | micro1 (posted as "Joblet-AI") | Staff Data Engineer (Remote) (LI 4489864062) | Remote, posted for India (and a UAE copy) | US$200–260k "national pay range" | ₹1.76 Cr if paid in USD | 62% | https://www.linkedin.com/jobs/view/4489864062 | The pay is probably the US range; India pay is unconfirmed. Wants greenfield platform builds and AI-agent tooling, which your resume doesn't show. Posted Nov 14. |
| 4 | Jobgether partner (unnamed) | Lead Data Engineer 4C (LI 4489198338) | Fully remote within India | not stated | unknown | 75% | https://www.linkedin.com/jobs/view/4489198338 | Azure/Databricks/Snowflake; leads a team; Azure DE cert preferred. A partner company handles applications; the employer isn't named. |
| 5 | Jobgether partner | Sr. Data Engineer 4B (LI 4489407254) | Fully remote, India | not stated | unknown | 72% | https://www.linkedin.com/jobs/view/4489407254 | Same partner; Databricks/Azure/Kafka. |
| 6 | Kake | Senior Data Engineer (Analyst/Scientist) – Remote (LI 4487157827 / 4488939709) | Fully remote, India; paid in USD | "Competitive USD" | unknown | 70% | https://www.linkedin.com/jobs/view/4487157827 | Contractor community; 5–6 h daily overlap with US Pacific time required. |
| 7 | OpenTable (Booking Holdings) | Senior Data Engineer (AI/ML) | 100% remote across India | not stated (form asks your minimum base) | unknown | 58% | https://job-boards.greenhouse.io/opentable/jobs/8817801002 | Open. Requires hands-on LLM/RAG/vector-DB experience, which your resume doesn't show. Strong employer. |
| 8 | EazyML | Senior Data Engineer – Microsoft Fabric (LI 4486881585) | Remote, anywhere in India | not stated | unknown | 80% | https://www.linkedin.com/jobs/view/4486881585 | 5+ yrs (mid-senior), so pay is likely under ₹42 L. 200+ applicants. |
| 9 | CloudLabs Inc | Sr. Data Engineer (India – Remote) (LI 4486026531) | Remote, India | not stated | unknown | 60% | https://www.linkedin.com/jobs/view/4486026531 | 10+ yrs; Snowflake/dbt/AWS Glue. Your AWS and Glue experience is thin. |

### REJECTED (short reasons)
- Juniper Square – Technical Lead (Data), India remote: React/TypeScript front-end experience mandatory.
- Juniper Square – Sr Business Analytics Engineer, India remote: needs Salesforce/NetSuite ARR metrics plus a semantic layer; weak match.
- Shuru – Lead Data Engineer, remote: needs Kafka/GCP/BigQuery/Terraform/K8s; stack mismatch.
- NPAworldwide – Analytics Solution Architect, APAC remote: needs JLPT N1/N2 Japanese.
- ClickHouse – Sr Cloud Data Infrastructure Eng (APJ): cloud infrastructure software role, not data engineering; Singapore-based.
- Binance – Sr Data Engineer, Square (APAC remote): Japan-located ML feature engineering role.
- Softview – AWS Data Engineer Lead ₹32–45 L: on-site in Chennai; minimum below threshold.
- Blumetra – Senior DE ₹15–24 L: below threshold; hybrid.
- Egen, XpertDox, Persistent, Marsh/Oliver Wyman, Fivetran, Commonwealth Bank, Atlassian, Novo Nordisk, etc.: India office/hybrid, not remote.
- BairesDev Azure/Databricks/dbt roles: LATAM-only hiring.
- Oportun Sr DE (R14287), Nearform Sr DE India, Level Access Sr DE, HighLevel Lead DE: closed (redirect or 404).
- Many US/UK/EU/Canada/Singapore/Australia senior roles: local location or work authorization required.
