"""Guided onboarding: what must be filled before each live action."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .core import get_rule
from .models import CompanyProfile, IntegrationAccount

FIELDS = [
    # key, label, required_for (set of actions), where
    ("website", "Official EpohTech website", {"draft"}, "profile"),
    ("description", "Company description", {"draft"}, "profile"),
    ("sender_name", "Business-development contact name", {"draft"}, "profile"),
    ("sender_title", "Designation", {"draft"}, "profile"),
    ("sender_email", "Verified company email (sender)", {"draft", "send_email"}, "profile"),
    ("postal_address", "Business postal address (anti-spam compliance)", {"send_email"}, "profile"),
    ("verified_facts", "Verified services / facts usable in messages", set(), "profile"),
    ("certifications", "Verified certifications", set(), "profile"),
    ("case_studies", "Approved case studies / references", set(), "profile"),
    ("delivery_capacity", "Actual consultants, experience, delivery capacity", {"send_email"}, "profile"),
    ("min_rates", "Minimum acceptable rates", set(), "profile"),
    ("target_countries", "Target countries", set(), "profile"),
    ("target_industries", "Target industries", set(), "profile"),
]


def checklist(db: Session) -> dict:
    p = db.scalar(select(CompanyProfile))
    items = []
    for key, label, req, _ in FIELDS:
        v = getattr(p, key, None) if p else None
        items.append({"key": key, "label": label, "done": bool(v), "required_for": sorted(req)})
    google = db.scalar(select(IntegrationAccount).where(IntegrationAccount.provider == "google"))
    s = get_settings()
    av = get_rule(db, "availability")
    items += [
        {"key": "email_account", "label": "Authorized email account (OAuth)", "required_for": ["send_email"],
         "done": bool(google and google.status == "connected" and s.email_provider != "mock")},
        {"key": "calendar", "label": "Calendar connected OR availability window confirmed", "required_for": ["book_meeting"],
         "done": bool((google and s.calendar_provider == "gcal") or av.get("confirmed_by_admin"))},
        {"key": "travel", "label": "Actual Dubai travel dates confirmed", "required_for": ["book_in_person"],
         "done": bool(get_rule(db, "campaign.dubai").get("confirmed_by_admin"))},
        {"key": "policy", "label": "Outreach approval policy chosen", "required_for": ["send_email"],
         "done": bool(get_rule(db, "approval.policy"))},
        {"key": "live_flag", "label": "ALLOW_LIVE_SEND=true in deployment env", "required_for": ["send_email"],
         "done": s.allow_live_send},
        {"key": "live_auth", "label": "Admin authorized live sending in Settings", "required_for": ["send_email"],
         "done": bool(get_rule(db, "system.live_send_authorized"))},
        {"key": "linkedin", "label": "LinkedIn: manual send (no partner API) — acknowledged", "required_for": [],
         "done": True},
    ]
    blocked = {}
    for act in ("draft", "send_email", "book_meeting", "book_in_person"):
        blocked[act] = [i["label"] for i in items if act in i["required_for"] and not i["done"]]
    return {"items": items, "blocked": blocked}


def can(db: Session, action: str) -> tuple[bool, list[str]]:
    b = checklist(db)["blocked"].get(action, [])
    return (not b), b
