"""Metrics computed directly from the database (single source of truth)."""
from __future__ import annotations

from collections import Counter
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .core import get_rule, now_utc
from .models import (Appointment, Evidence, LeadStatus, Message, MessageStatus, Opportunity, Organization)

OUT_DONE = [MessageStatus.SENT, MessageStatus.ACKNOWLEDGED, MessageStatus.BOUNCED]


def overview(db: Session) -> dict:
    c = lambda q: db.scalar(q) or 0  # noqa: E731
    sent = c(select(func.count(Message.id)).where(Message.direction == "out", Message.status.in_(OUT_DONE)))
    replied_contacts = c(select(func.count(func.distinct(Message.contact_id))).where(Message.direction == "in"))
    positive = c(select(func.count(Message.id)).where(Message.direction == "in", Message.classification.in_(
        ["interested", "meeting", "requesting_info", "requesting_proposal", "referral"])))
    cfg = get_rule(db, "campaign.dubai")
    travel = date.fromisoformat(cfg["travel_date"])
    today = now_utc().date()
    return {
        "leads_discovered": c(select(func.count(Organization.id))),
        "qualified": c(select(func.count(Organization.id)).where(Organization.tier.in_(["A", "B"]))),
        "tier_a": c(select(func.count(Organization.id)).where(Organization.tier == "A")),
        "outreach_sent": sent,
        "dry_run": c(select(func.count(Message.id)).where(Message.status == MessageStatus.DRY_RUN)),
        "manual_pending": c(select(func.count(Message.id)).where(Message.status == MessageStatus.MANUAL_PENDING)),
        "awaiting_approval": c(select(func.count(Message.id)).where(Message.status == MessageStatus.DRAFTED)),
        "response_rate": round(100 * replied_contacts / sent, 1) if sent else 0.0,
        "positive_responses": positive,
        "meetings_proposed": c(select(func.count(Appointment.id)).where(Appointment.status == "PROPOSED")),
        "meetings_confirmed": c(select(func.count(Appointment.id)).where(Appointment.status.in_(["CONFIRMED", "RESCHEDULED", "COMPLETED"]))),
        "in_person": c(select(func.count(Appointment.id)).where(Appointment.format == "in_person", Appointment.status.in_(["CONFIRMED", "RESCHEDULED", "COMPLETED"]))),
        "remote_meetings": c(select(func.count(Appointment.id)).where(Appointment.format == "remote", Appointment.status.in_(["CONFIRMED", "RESCHEDULED", "COMPLETED"]))),
        "pending_responses": c(select(func.count(Organization.id)).where(Organization.status == LeadStatus.SENT)),
        "follow_ups_due": c(select(func.count(Organization.id)).where(Organization.status == LeadStatus.FOLLOW_UP_DUE)),
        "needs_review": c(select(func.count(Organization.id)).where(Organization.status == LeadStatus.NEEDS_REVIEW)),
        "remote_opportunities": c(select(func.count(Opportunity.id)).where(Opportunity.remote_eligibility.in_(["india_ok", "global"]))),
        "days_to_dubai": (travel - today).days,
        "dubai_trip_passed": today > travel,
    }


def detailed(db: Session) -> dict:
    orgs = list(db.scalars(select(Organization)))
    msgs = list(db.scalars(select(Message)))
    channel = Counter((m.channel, m.status.value) for m in msgs if m.direction == "out")
    sources = Counter(e.source_name for e in db.scalars(select(Evidence)))
    services = Counter(s for o in orgs if o.tier in ("A", "B") for e in o.evidence for s in e.matched_services)
    funnel = Counter(o.status.value for o in orgs)
    outcomes = Counter(a.status for a in db.scalars(select(Appointment)))
    variants = Counter((m.template_key, m.variant) for m in msgs if m.direction == "out" and m.kind == "intro")
    return {"channel": {f"{k[0]}:{k[1]}": v for k, v in channel.items()}, "lead_sources": dict(sources),
            "top_services": services.most_common(10), "funnel": dict(funnel), "meeting_outcomes": dict(outcomes),
            "intro_variants": {f"{k[0]}/{k[1]}": v for k, v in variants.items()},
            "synthetic_records": sum(1 for o in orgs if o.is_synthetic)}
