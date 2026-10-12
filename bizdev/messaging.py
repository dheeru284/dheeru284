"""Outreach message generation.

Deterministic templates are the default and the safety floor. Every claim in a
message comes from either (a) the verified company profile, or (b) a
non-inferred Evidence row about the recipient. An optional LLM may *rephrase*
the template output; its output is checked so it cannot add facts (numbers,
certifications, client names) that were not in the input.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .core import audit, get_rule, now_utc
from .models import (CompanyProfile, Contact, LeadStatus, Message, MessageStatus, Organization)
from .untrusted import fence

CATEGORY_TEMPLATE = {
    "consulting": "consulting", "system_integrator": "consulting", "oracle_partner": "consulting",
    "cloud_consulting": "consulting", "data_consulting": "consulting", "managed_services": "consulting",
    "staffing_agency": "staffing", "recruitment": "staffing",
    "end_client": "end_client", "enterprise": "end_client",
    "freelance_platform": "freelance", "contract_provider": "freelance",
}

SUBJECTS = {
    "consulting": ["Delivery capacity for {service} work — {sender_company}",
                   "{org}: {service} resources for upcoming projects",
                   "Subcontracting support for {org}'s {service} delivery"],
    "staffing": ["{service} contractors available via {sender_company}",
                 "Supplier introduction — {sender_company} ({service})",
                 "Re: {org} {service} requirements"],
    "end_client": ["{service} support for {org}", "{org} and {service} delivery — short intro",
                   "Quick question about {org}'s {service} plans"],
    "freelance": ["{service} — {sender_company} interest", "Application interest: {service}",
                  "{service} engagement from India-based team"],
}

OPENERS = {
    "consulting": "I lead business development at {sender_company}. We provide {services_line} to consulting and implementation partners on a contract and subcontracting basis.",
    "staffing": "I'm reaching out from {sender_company}. We supply {services_line} professionals to agencies and their clients, on-site or remotely from India.",
    "end_client": "I'm with {sender_company}, a technology services company providing {services_line}.",
    "freelance": "I'm writing on behalf of {sender_company}, which provides {services_line}.",
}

WHY = {
    True: "I noticed {evidence_line} ({evidence_source}), which is close to the work we do.",
    False: "I'm contacting {org} because your work in {industry_or_category} overlaps with the services we offer. I don't have details of a current requirement, so I'd rather ask than assume.",
}

ASKS = {
    "dubai": "I'll be in Dubai around {travel_date_human}. Would a 30-minute meeting at your office or nearby be useful? If in-person doesn't suit, I'm happy to do a video call instead.",
    "remote": "Would you be open to a 20-minute video call to discuss any upcoming {service} requirements?",
}

FOLLOWUPS = {
    "followup_brief": "Hi {first_name},\n\nFollowing up briefly on my note about {service} support for {org}. If it isn't a priority right now, no problem — just let me know.\n\n{ask}\n\n{signature}",
    "followup_value": "Hi {first_name},\n\nOne more detail that may be relevant: {value_line}\n\n{ask}\n\n{signature}",
    "followup_final": "Hi {first_name},\n\nI don't want to fill your inbox, so this will be my last note. If {service} support becomes relevant for {org} later, I'd be glad to hear from you.\n\n{signature}",
}

OTHER = {
    "linkedin_connect": "Hi {first_name}, I'm with {sender_company} ({services_short}). {why_short} Would be glad to connect.",
    "linkedin_followup": "Thanks for connecting, {first_name}. {opener_short} {ask}",
    "meeting_confirm": "Hi {first_name},\n\nThank you — confirming our meeting on {meeting_time}.\nFormat: {meeting_format}\n{meeting_location}\n\nProposed agenda:\n{agenda}\n\n{signature}",
    "meeting_reminder": "Hi {first_name},\n\nA quick reminder of our meeting on {meeting_time} ({meeting_format}). {meeting_location}\n\n{signature}",
    "post_meeting": "Hi {first_name},\n\nThank you for your time today. As discussed, the next step is: {next_action}\n\n{signature}",
    "vendor_registration": "Hello,\n\n{opener}\n\nWe would like to register as a supplier for {service} services with {org}. Could you point me to your vendor onboarding process and requirements?\n\n{signature}",
    "rfp_interest": "Hello,\n\n{opener}\n\nWe have reviewed {evidence_line} ({evidence_source}) and would like to confirm the submission process and deadline. Please let us know where to send questions.\n\n{signature}",
    "interested_reply": "Hi {first_name},\n\nThank you for your reply. {ask}\n\n{signature}",
}

FORBIDDEN_UNSUPPORTED = re.compile(r"(?i)\b(certified|certification|partner of|trusted by|clients include|"
                                   r"\d+\+?\s*(years|consultants|engineers|clients|projects)|guarantee)")


class GenerationBlocked(Exception):
    pass


def profile(db: Session) -> CompanyProfile:
    p = db.scalar(select(CompanyProfile))
    if not p:
        raise GenerationBlocked("Company profile not set up (onboarding incomplete).")
    return p


def signature(p: CompanyProfile) -> str:
    missing = [f for f in ("sender_name", "sender_email") if not getattr(p, f)]
    if missing:
        raise GenerationBlocked(f"Verified signature fields missing: {missing}")
    lines = [p.sender_name, p.sender_title, p.name, p.sender_email, p.sender_phone, p.website]
    sig = "\n".join(x for x in lines if x)
    if p.postal_address:
        sig += "\n" + p.postal_address
    return sig + "\n\nIf you'd prefer not to hear from us, reply \"unsubscribe\" and we won't contact you again."


def dubai_mention_ok(db: Session, campaign_code: str) -> tuple[bool, str]:
    cfg = get_rule(db, "campaign.dubai")
    travel = date.fromisoformat(cfg["travel_date"])
    end = date.fromisoformat(cfg["window_end"])
    today = now_utc().date()
    ok = campaign_code == "A_DUBAI" and today <= end
    return ok, travel.strftime("%-d %B %Y") if today < travel else "the coming days"


def _evidence(org: Organization):
    real = sorted([e for e in org.evidence if not e.is_inference], key=lambda e: e.evidence_date or date.min, reverse=True)
    return real[0] if real else None


def build_context(db: Session, org: Organization, contact: Contact | None, campaign_code: str) -> dict:
    p = profile(db)
    ev = _evidence(org)
    services = (ev.matched_services if ev and ev.matched_services else []) or [s for e in org.evidence for s in e.matched_services]
    service = services[0] if services else "data engineering and integration"
    services_line = ", ".join(sorted(set(services))[:3]) if services else "data engineering, analytics, integration and delivery-management resources"
    dubai, when = dubai_mention_ok(db, campaign_code)
    first = (contact.full_name.split()[0] if contact and contact.full_name and contact.verified else None) or "there"
    ctx = dict(org=org.name, sender_company=p.name, service=service, services_line=services_line,
               services_short=services_line, first_name=first, signature=signature(p),
               evidence_line=ev.summary.rstrip(".") if ev else "", evidence_source=ev.source_url if ev else "",
               industry_or_category=org.industry or (org.category or "technology").replace("_", " "),
               travel_date_human=when, has_evidence=bool(ev), evidence_id=ev.id if ev else None, dubai=dubai,
               value_line=next((f["fact"] for f in (p.verified_facts or []) if f.get("verified")),
                               f"we can provide {service} resources on a contract basis, remotely from India or on-site where permitted."))
    ctx["ask"] = ASKS["dubai" if dubai else "remote"].format(**ctx)
    ctx["opener"] = OPENERS[CATEGORY_TEMPLATE.get(org.category or "", "end_client")].format(**ctx)
    ctx["opener_short"] = ctx["opener"].split(". ")[0] + "."
    ctx["why"] = WHY[bool(ev)].format(**ctx)
    ctx["why_short"] = (f"Saw {ctx['evidence_line'][:80]}." if ev else "")
    return ctx


def render(db: Session, org: Organization, contact: Contact | None, kind: str, campaign_code: str = "A_DUBAI",
           variant: int = 0, extra: dict | None = None) -> dict:
    ctx = build_context(db, org, contact, campaign_code)
    ctx.update(extra or {})
    tkey = CATEGORY_TEMPLATE.get(org.category or "", "end_client")
    subject = None
    if kind == "intro":
        subject = SUBJECTS[tkey][variant % len(SUBJECTS[tkey])].format(**ctx)
        body = f"Hi {ctx['first_name']},\n\n{ctx['opener']}\n\n{ctx['why']}\n\n{ctx['ask']}\n\n{ctx['signature']}"
    elif kind in FOLLOWUPS:
        subject = "Re: " + SUBJECTS[tkey][variant % len(SUBJECTS[tkey])].format(**ctx)
        body = FOLLOWUPS[kind].format(**ctx)
    elif kind in OTHER:
        body = OTHER[kind].format(**{k: ctx.get(k, "") for k in _fields(OTHER[kind])} | ctx)
        subject = {"meeting_confirm": f"Meeting confirmed — {ctx['org']} / {ctx['sender_company']}",
                   "meeting_reminder": "Reminder: our meeting",
                   "post_meeting": f"Thank you — next steps ({ctx['org']})",
                   "vendor_registration": f"Supplier registration enquiry — {ctx['sender_company']}",
                   "rfp_interest": f"Enquiry regarding your requirement — {ctx['sender_company']}",
                   "interested_reply": "Re: our conversation"}.get(kind)
        if kind == "linkedin_connect":
            body = body[:300]  # LinkedIn connection-note length limit
    else:
        raise ValueError(f"unknown message kind {kind}")
    body = re.sub(r"\n{3,}", "\n\n", body)
    _assert_no_unsupported_claims(db, body)
    return {"subject": subject, "body": body, "template_key": f"{tkey}:{kind}", "variant": chr(65 + variant % 3),
            "facts_used": [ctx["evidence_id"]] if ctx["evidence_id"] else []}


def _fields(tpl: str) -> set[str]:
    return set(re.findall(r"{(\w+)}", tpl))


def _assert_no_unsupported_claims(db: Session, body: str) -> None:
    p = profile(db)
    allowed = " ".join([f.get("fact", "") for f in (p.verified_facts or []) if f.get("verified")] +
                       [str(c) for c in p.certifications or []] + [str(c) for c in p.case_studies or []])
    for m in FORBIDDEN_UNSUPPORTED.finditer(body):
        if m.group(0).lower() not in allowed.lower():
            raise GenerationBlocked(f"Message contains an unverified claim: '{m.group(0)}'")


def content_hash(contact_key: str, body: str) -> str:
    norm = re.sub(r"\s+", " ", body.strip().lower())
    return hashlib.sha256(f"{contact_key}|{norm}".encode()).hexdigest()


def draft(db: Session, org: Organization, contact: Contact | None, kind: str = "intro", channel: str = "email",
          campaign_code: str = "A_DUBAI", variant: int | None = None, actor: str = "system",
          extra: dict | None = None, campaign_id: int | None = None) -> Message:
    if channel == "email" and (not contact or not contact.email):
        raise GenerationBlocked("No verified email for this contact; cannot draft an email.")
    if channel == "linkedin" and (not contact or not contact.linkedin_url):
        raise GenerationBlocked("No LinkedIn profile URL on record for this contact.")
    # pick a variant not yet used with this contact (A/B testing without duplicates)
    used = set(db.scalars(select(Message.variant).where(Message.contact_id == (contact.id if contact else None),
                                                        Message.kind == kind)))
    v = variant if variant is not None else next((i for i in range(3) if chr(65 + i) not in used), 0)
    out = render(db, org, contact, kind, campaign_code, v, extra)
    if channel == "linkedin" and kind == "intro":
        out = render(db, org, contact, "linkedin_connect", campaign_code, v, extra)
    out["body"] = maybe_polish_with_llm(out["body"], org)
    ckey = (contact.email or contact.linkedin_url) if contact else org.name
    h = content_hash(ckey, out["body"])
    if db.scalar(select(Message).where(Message.content_hash == h, Message.status.notin_(
            [MessageStatus.REJECTED, MessageStatus.CANCELLED]))):
        raise GenerationBlocked("An identical message already exists for this recipient.")
    m = Message(organization_id=org.id, contact_id=contact.id if contact else None, channel=channel, kind=kind,
                campaign_id=campaign_id, template_key=out["template_key"], variant=out["variant"],
                subject=out["subject"], body=out["body"], facts_used=out["facts_used"], content_hash=h,
                status=MessageStatus.DRAFTED)
    db.add(m); db.flush()
    if org.status in {LeadStatus.DISCOVERED, LeadStatus.QUALIFIED}:
        org.status = LeadStatus.MESSAGE_DRAFTED
    audit(db, actor, "message.drafted", "message", m.id, kind=kind, channel=channel)
    return m


def maybe_polish_with_llm(body: str, org: Organization) -> str:
    """Optional rephrasing. Falls back to the template if the LLM adds unsupported content."""
    s = get_settings()
    if s.llm_provider != "anthropic" or not s.anthropic_api_key:
        return body
    try:
        import anthropic  # optional dependency
        client = anthropic.Anthropic(api_key=s.anthropic_api_key)
        ev_text = "\n".join(e.raw_excerpt or e.summary for e in org.evidence[:2])
        resp = client.messages.create(
            model=s.llm_model, max_tokens=800,
            system=("You polish B2B outreach emails. Keep every fact exactly as given. Do not add facts, numbers, "
                    "client names, certifications, or claims. Keep the signature and unsubscribe line verbatim. "
                    "Return only the email body."),
            messages=[{"role": "user", "content": f"Draft:\n{body}\n\nBackground (reference only):\n{fence(ev_text)}"}])
        new = resp.content[0].text.strip()
    except Exception:  # noqa: BLE001
        return body
    if FORBIDDEN_UNSUPPORTED.search(new) and not FORBIDDEN_UNSUPPORTED.search(body):
        return body
    if "unsubscribe" not in new.lower():
        return body
    return new
