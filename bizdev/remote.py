"""Campaign B: remote / freelance / contract opportunities deliverable from India."""
from __future__ import annotations

import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .core import audit, now_utc
from .discovery import match_services
from .models import Application, Opportunity
from .untrusted import clean_text

INDIA_OK = re.compile(r"(?i)\b(india|apac|asia|worldwide|anywhere|global(ly)? remote|work from anywhere|offshore)\b")
RESTRICT = re.compile(r"(?i)\b(us only|usa only|uk only|eu only|must (be|reside) in|right to work in|"
                      r"work authori[sz]ation|citizens? only|security clearance|green card|residen(cy|t) (in|of))\b")
ONSITE = re.compile(r"(?i)\b(on-?site|in[- ]office|hybrid|relocat)")


def assess(text: str, remote_flag: bool | None) -> tuple[str, list[str]]:
    t = clean_text(text, 8000)
    flags = []
    if RESTRICT.search(t):
        flags.append("country_or_work_authorization_restriction")
    if ONSITE.search(t):
        flags.append("physical_presence_required")
    if "local employ" in t.lower() or "payroll" in t.lower():
        flags.append("local_employment_possible")
    if remote_flag is False or "physical_presence_required" in flags and not INDIA_OK.search(t):
        elig = "onsite"
    elif flags and "country_or_work_authorization_restriction" in flags:
        elig = "restricted"
    elif re.search(r"(?i)\bindia\b", t):
        elig = "india_ok"
    elif INDIA_OK.search(t):
        elig = "global"
    else:
        elig = "unknown"
    return elig, flags


def score(db: Session, o: Opportunity, text: str) -> int:
    s = 0
    s += {"india_ok": 35, "global": 25, "unknown": 10, "restricted": 0, "onsite": 0}[o.remote_eligibility]
    s += min(len(match_services(db, text)), 3) * 10
    if o.evidence_date and (now_utc().date() - o.evidence_date).days <= 30:
        s += 15
    if o.deadline and o.deadline < now_utc().date():
        s = 0
    if o.compensation_min is not None:
        s += 10  # published compensation = more transparent opportunity
    if o.contract_type and re.search(r"(?i)contract|freelance|consult", o.contract_type):
        s += 10
    return min(s, 100)


def add_opportunity(db: Session, *, title: str, source_url: str, text: str, actor: str = "discovery",
                    organization_id: int | None = None, remote: bool | None = None, **fields) -> Opportunity:
    if not source_url.startswith(("http://", "https://")):
        raise ValueError("source_url required")
    existing = db.scalar(select(Opportunity).where(Opportunity.source_url == source_url))
    if existing:
        return existing
    elig, flags = assess(text, remote)
    # Compensation/duration only if explicitly provided by the source; never estimated.
    o = Opportunity(title=title, source_url=source_url, organization_id=organization_id, scope=clean_text(text, 2000),
                    remote_eligibility=elig, flags=flags, required_skills=match_services(db, text), **fields)
    db.add(o); db.flush()
    o.score = score(db, o, text)
    audit(db, actor, "opportunity.added", "opportunity", o.id, eligibility=elig, score=o.score)
    return o


def authorize_application(db: Session, o: Opportunity, actor: str) -> Application:
    """Records human authorization. Submission itself is manual (via the posting's own method)."""
    a = db.scalar(select(Application).where(Application.opportunity_id == o.id)) or Application(opportunity_id=o.id)
    a.status, a.authorized_by = "AUTHORIZED", actor
    o.status = "APPLY_APPROVED"
    db.add(a)
    audit(db, actor, "application.authorized", "opportunity", o.id)
    return a


def mark_applied(db: Session, o: Opportunity, actor: str, notes: str = "") -> Application:
    a = db.scalar(select(Application).where(Application.opportunity_id == o.id))
    if not a or a.status != "AUTHORIZED":
        raise PermissionError("Application must be authorized before it is marked submitted.")
    a.status, a.submitted_at, a.notes = "SUBMITTED", now_utc(), notes
    o.status = "APPLIED"
    audit(db, actor, "application.submitted", "opportunity", o.id)
    return a


def upcoming_deadlines(db: Session, days: int = 14) -> list[Opportunity]:
    today = now_utc().date()
    return [o for o in db.scalars(select(Opportunity).where(Opportunity.deadline.is_not(None)))
            if today <= o.deadline <= date.fromordinal(today.toordinal() + days)]
