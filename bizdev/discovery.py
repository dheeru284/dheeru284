"""Lead discovery: source adapters -> normalized leads -> dedup -> evidence -> score.

Adapters return `RawLead`s. Every lead must carry a source URL; anything a
source did not state explicitly must be marked `is_inference=True`.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Protocol
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .core import audit
from .models import Contact, Evidence, Organization, ServiceOffering
from .scoring import qualify
from .untrusted import clean_text, injection_suspected

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
GENERIC_SUFFIXES = re.compile(r"\b(private|pvt|limited|ltd|llc|l\.l\.c|fze|fz-llc|fzco|inc|gmbh|plc|co)\b\.?", re.I)
DECISION_ROLES = re.compile(r"(?i)\b(founder|managing director|ceo|cto|cio|head of|director|vp|vice president|"
                            r"practice lead|procurement|vendor manag|resource manag|workforce|hiring manager|"
                            r"talent acquisition lead|business development)\b")


@dataclass
class RawContact:
    full_name: str | None = None
    role: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    source_url: str | None = None
    verified: bool = False  # source explicitly shows this person in this role at this org


@dataclass
class RawLead:
    company_name: str
    source_name: str
    source_url: str
    signal_type: str
    summary: str
    website: str | None = None
    country: str | None = None
    city: str | None = None
    industry: str | None = None
    category: str | None = None
    evidence_date: date | None = None
    remote_ok: bool | None = None
    is_inference: bool = False
    raw_excerpt: str | None = None
    contacts: list[RawContact] = field(default_factory=list)
    is_synthetic: bool = False


class LeadSource(Protocol):
    name: str
    def fetch(self, query: dict) -> Iterable[RawLead]: ...


def normalize_name(name: str) -> str:
    n = GENERIC_SUFFIXES.sub(" ", name.lower())
    return re.sub(r"[^a-z0-9]+", " ", n).strip()


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url if "://" in url else "https://" + url).hostname or ""
    return host.lower().removeprefix("www.") or None


def match_services(db: Session, text: str) -> list[str]:
    t = (text or "").lower()
    out = []
    for s in db.scalars(select(ServiceOffering).where(ServiceOffering.active.is_(True))):
        kws = [s.title.lower(), *[k.lower() for k in (s.keywords or [])]]
        if any(re.search(r"\b" + re.escape(k) + r"\b", t) for k in kws if k):
            out.append(s.title)
    return out


def find_org(db: Session, name: str, website: str | None) -> Organization | None:
    d = domain_of(website)
    if d:
        org = db.scalar(select(Organization).where(Organization.domain == d))
        if org:
            return org
    return db.scalar(select(Organization).where(Organization.normalized_name == normalize_name(name)))


def find_contact(db: Session, email: str | None, linkedin: str | None, org_id: int, name: str | None) -> Contact | None:
    if email:
        c = db.scalar(select(Contact).where(Contact.email == email.lower()))
        if c:
            return c
    if linkedin:
        c = db.scalar(select(Contact).where(Contact.linkedin_url == linkedin.rstrip("/")))
        if c:
            return c
    if name:
        for c in db.scalars(select(Contact).where(Contact.organization_id == org_id)):
            if c.full_name and normalize_name(c.full_name) == normalize_name(name):
                return c
    return None


def ingest(db: Session, raw: RawLead, campaign_code: str = "A_DUBAI", actor: str = "discovery") -> tuple[Organization, bool]:
    """Upsert one lead. Returns (org, created). Never invents fields the source did not give."""
    if not raw.source_url or not raw.source_url.startswith(("http://", "https://")):
        raise ValueError("every lead needs an http(s) source_url")
    summary = clean_text(raw.summary, 1000)
    excerpt = clean_text(raw.raw_excerpt, 4000) if raw.raw_excerpt else None
    flagged = injection_suspected((raw.summary or "") + " " + (raw.raw_excerpt or ""))

    org = find_org(db, raw.company_name, raw.website)
    created = org is None
    if created:
        org = Organization(name=raw.company_name.strip(), normalized_name=normalize_name(raw.company_name),
                           domain=domain_of(raw.website), website=raw.website, country=raw.country, city=raw.city,
                           industry=raw.industry, category=raw.category, is_synthetic=raw.is_synthetic)
        db.add(org); db.flush()
        audit(db, actor, "lead.discovered", "organization", org.id, source=raw.source_url)
    else:
        for f in ("website", "country", "city", "industry", "category"):
            if not getattr(org, f) and getattr(raw, f):
                setattr(org, f, getattr(raw, f))
        if not org.domain and raw.website:
            org.domain = domain_of(raw.website)

    exists = db.scalar(select(Evidence).where(Evidence.organization_id == org.id, Evidence.source_url == raw.source_url,
                                              Evidence.signal_type == raw.signal_type))
    if not exists:
        db.add(Evidence(organization_id=org.id, source_name=raw.source_name, source_url=raw.source_url,
                        signal_type=raw.signal_type, summary=summary, raw_excerpt=excerpt,
                        evidence_date=raw.evidence_date, is_inference=raw.is_inference, remote_ok=raw.remote_ok,
                        matched_services=match_services(db, summary + " " + (excerpt or ""))))
    if flagged:
        audit(db, actor, "untrusted.injection_suspected", "organization", org.id, level="warn", source=raw.source_url)

    for rc in raw.contacts:
        email = rc.email.lower().strip() if rc.email and EMAIL_RE.match(rc.email.strip()) else None
        li = rc.linkedin_url.rstrip("/") if rc.linkedin_url else None
        c = find_contact(db, email, li, org.id, rc.full_name)
        if c:
            audit(db, actor, "contact.duplicate", "contact", c.id)
            c.verified = c.verified or rc.verified
            c.email = c.email or email
            c.linkedin_url = c.linkedin_url or li
            continue
        db.add(Contact(organization_id=org.id, full_name=rc.full_name, role=rc.role, email=email, linkedin_url=li,
                       source_url=rc.source_url or raw.source_url, verified=rc.verified,
                       is_decision_maker=bool(rc.role and DECISION_ROLES.search(rc.role))))
    db.flush(); db.refresh(org)
    qualify(db, org, campaign_code, actor)
    return org, created


# ---------------------------------------------------------------- adapters

class CSVImportSource:
    """Manual / exported research (e.g. from a sales navigator export the user is licensed for)."""
    name = "csv_import"
    REQUIRED = {"company_name", "source_url", "signal_type", "summary"}

    def __init__(self, text: str):
        self.text = text

    def fetch(self, query: dict | None = None) -> Iterable[RawLead]:
        rd = csv.DictReader(io.StringIO(self.text))
        missing = self.REQUIRED - set(rd.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing columns: {sorted(missing)}")
        for r in rd:
            contacts = []
            if r.get("contact_name") or r.get("contact_email") or r.get("contact_linkedin"):
                contacts.append(RawContact(full_name=r.get("contact_name") or None, role=r.get("contact_role") or None,
                                           email=r.get("contact_email") or None,
                                           linkedin_url=r.get("contact_linkedin") or None,
                                           verified=(r.get("contact_verified", "").lower() in {"1", "true", "yes"})))
            ro = (r.get("remote_ok") or "").lower()
            yield RawLead(company_name=r["company_name"], source_name=r.get("source_name") or self.name,
                          source_url=r["source_url"], signal_type=r["signal_type"], summary=r["summary"],
                          website=r.get("website") or None, country=r.get("country") or None,
                          city=r.get("city") or None, industry=r.get("industry") or None,
                          category=r.get("category") or None,
                          evidence_date=date.fromisoformat(r["evidence_date"]) if r.get("evidence_date") else None,
                          remote_ok=True if ro in {"true", "yes", "1"} else False if ro in {"false", "no", "0"} else None,
                          is_inference=(r.get("is_inference", "").lower() in {"1", "true", "yes"}), contacts=contacts)


class ApolloSource:
    """Apollo.io people search (requires APOLLO_API_KEY and an Apollo plan that allows API use).

    Apollo returns people/org records, not proof of an active project, so leads
    from here are recorded with signal_type='directory_listing' and must be
    paired with real requirement evidence before they can reach Tier A.
    Implemented against Apollo's documented REST API; NOT verified live from this environment.
    """
    name = "apollo"
    URL = "https://api.apollo.io/api/v1/mixed_people/search"

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or get_settings().apollo_api_key
        self.client = client or httpx.Client(timeout=20)

    def fetch(self, query: dict) -> Iterable[RawLead]:
        if not self.api_key:
            raise RuntimeError("Apollo not configured (APOLLO_API_KEY missing)")
        r = self.client.post(self.URL, headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"},
                             json={"person_titles": query.get("titles", []),
                                   "organization_locations": query.get("locations", []),
                                   "q_keywords": query.get("keywords", ""), "page": 1, "per_page": 25})
        r.raise_for_status()
        for p in r.json().get("people", []):
            org = p.get("organization") or {}
            if not org.get("name"):
                continue
            url = p.get("linkedin_url") or org.get("website_url")
            if not url:
                continue
            yield RawLead(company_name=org["name"], source_name="apollo", source_url=url,
                          signal_type="directory_listing",
                          summary=f"Apollo directory record: {p.get('title') or 'contact'} at {org['name']}",
                          website=org.get("website_url"), country=p.get("country"), city=p.get("city"),
                          industry=org.get("industry"), contacts=[RawContact(
                              full_name=p.get("name"), role=p.get("title"),
                              email=p.get("email") if p.get("email_status") == "verified" else None,
                              linkedin_url=p.get("linkedin_url"), verified=bool(p.get("title")))])


class StaticSource:
    """In-memory source used by tests and the synthetic seed."""
    def __init__(self, name: str, leads: list[RawLead]):
        self.name, self.leads = name, leads

    def fetch(self, query: dict | None = None) -> Iterable[RawLead]:
        return list(self.leads)


def run_source(db: Session, source: LeadSource, query: dict | None = None, campaign_code: str = "A_DUBAI") -> dict:
    stats = {"seen": 0, "created": 0, "updated": 0, "errors": 0}
    try:
        leads = list(source.fetch(query or {}))
    except Exception as e:  # noqa: BLE001 - surface, never silently succeed
        audit(db, "discovery", "source.failed", level="error", source=source.name, error=str(e)[:500])
        db.commit()
        raise
    for raw in leads:
        stats["seen"] += 1
        try:
            _, created = ingest(db, raw, campaign_code)
            stats["created" if created else "updated"] += 1
        except ValueError as e:
            stats["errors"] += 1
            audit(db, "discovery", "lead.rejected", level="warn", reason=str(e), company=raw.company_name)
    stats["auto_drafted"] = auto_draft(db, campaign_code)
    audit(db, "discovery", "source.run", source=source.name, **stats)
    db.commit()
    return stats


def auto_draft(db: Session, campaign_code: str) -> int:
    """Draft one intro per qualified (Tier A/B) lead that has an email contact and no message yet.
    Drafts still need human approval before anything is sent."""
    from .core import get_rule
    from .messaging import GenerationBlocked, draft
    from .models import LeadStatus, Message
    from .outreach import is_suppressed
    if not get_rule(db, "auto_draft.on_import"):
        return 0
    n = 0
    for org in db.scalars(select(Organization).where(Organization.tier.in_(["A", "B"]),
                                                     Organization.status == LeadStatus.QUALIFIED)):
        if db.scalar(select(Message.id).where(Message.organization_id == org.id)):
            continue
        c = next((c for c in sorted(org.contacts, key=lambda c: (not c.is_decision_maker, not c.verified))
                  if c.email and not is_suppressed(db, c)), None)
        if not c:
            continue
        try:
            with db.begin_nested():
                draft(db, org, c, kind="intro", channel="email", campaign_code=campaign_code, actor="auto_draft")
            n += 1
        except GenerationBlocked as e:
            audit(db, "auto_draft", "draft.skipped", "organization", org.id, reason=str(e)[:200])
    return n
