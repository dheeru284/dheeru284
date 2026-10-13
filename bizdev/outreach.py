"""Approval workflow, guarded dispatch, follow-ups, reply handling, and the job queue."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .config import get_settings
from .core import audit, get_rule, now_utc
from .integrations.email import InboundEmail, OutboundEmail, SendError
from .integrations.linkedin import LinkedInActionBlocked
from .messaging import GenerationBlocked, draft, profile
from .models import (Contact, Job, LeadStatus, Message, MessageStatus, Organization, Suppression, Thread)
from .providers import registry

STOP_STATES = {LeadStatus.NOT_INTERESTED, LeadStatus.UNSUBSCRIBED, LeadStatus.DO_NOT_CONTACT,
               LeadStatus.CLOSED, LeadStatus.BOUNCED}
ENGAGED_STATES = {LeadStatus.REPLIED, LeadStatus.MEETING_PROPOSED, LeadStatus.MEETING_BOOKED, LeadStatus.COMPLETED,
                  LeadStatus.NEEDS_REVIEW}
COUNTED = [MessageStatus.SENT, MessageStatus.DRY_RUN, MessageStatus.MANUAL_PENDING, MessageStatus.ACKNOWLEDGED]
MAX_ATTEMPTS = 4
# Best-effort default zone per country when the contact's zone is unknown (multi-zone countries use the main business hub).
COUNTRY_TZ = {"AE": "Asia/Dubai", "UAE": "Asia/Dubai", "IN": "Asia/Kolkata", "INDIA": "Asia/Kolkata",
              "GB": "Europe/London", "UK": "Europe/London", "SA": "Asia/Riyadh", "QA": "Asia/Qatar",
              "OM": "Asia/Muscat", "BH": "Asia/Bahrain", "KW": "Asia/Kuwait", "SG": "Asia/Singapore",
              "DE": "Europe/Berlin", "NL": "Europe/Amsterdam", "IE": "Europe/Dublin", "FR": "Europe/Paris",
              "US": "America/New_York", "CA": "America/Toronto", "AU": "Australia/Sydney"}


class DispatchBlocked(Exception):
    pass


# ------------------------------------------------------------------ controls

def live_sending_enabled(db: Session) -> bool:
    """Both the deployment flag AND the in-app admin authorization must be on."""
    return get_settings().allow_live_send and bool(get_rule(db, "system.live_send_authorized"))


def halted(db: Session) -> str | None:
    if get_rule(db, "system.emergency_stop"):
        return "emergency_stop"
    if get_rule(db, "system.paused"):
        return "paused"
    return None


def emergency_stop(db: Session, actor: str, on: bool = True) -> int:
    from .core import set_rule
    set_rule(db, "system.emergency_stop", on, actor)
    n = 0
    if on:
        for j in db.scalars(select(Job).where(Job.status == "PENDING", Job.kind.in_(["dispatch", "followup"]))):
            j.status = "CANCELLED"; j.last_error = "emergency stop"; n += 1
        for m in db.scalars(select(Message).where(Message.status == MessageStatus.QUEUED)):
            m.status = MessageStatus.APPROVED  # back to awaiting dispatch; nothing goes out
    audit(db, actor, "system.emergency_stop", detail_on=on, cancelled_jobs=n, level="warn")
    db.commit()
    return n


# ------------------------------------------------------------------ suppression

def is_suppressed(db: Session, contact: Contact | None) -> str | None:
    if not contact:
        return None
    vals = []
    if contact.email:
        vals += [("email", contact.email.lower()), ("domain", contact.email.split("@")[-1].lower())]
    if contact.linkedin_url:
        vals.append(("linkedin", contact.linkedin_url))
    for k, v in vals:
        s = db.scalar(select(Suppression).where(Suppression.kind == k, Suppression.value == v))
        if s:
            return s.reason
    org = contact.organization
    if org and org.status in STOP_STATES:
        return org.status.value
    return None


def suppress(db: Session, contact: Contact, reason: str, actor: str, org_status: LeadStatus | None = None) -> None:
    for k, v in (("email", contact.email), ("linkedin", contact.linkedin_url)):
        if v and not db.scalar(select(Suppression).where(Suppression.kind == k, Suppression.value == v.lower() if k == "email" else v)):
            db.add(Suppression(kind=k, value=v.lower() if k == "email" else v, reason=reason, source=actor))
    # cancel everything pending for this contact
    for m in db.scalars(select(Message).where(Message.contact_id == contact.id, Message.direction == "out",
                                              Message.status.in_([MessageStatus.DRAFTED, MessageStatus.APPROVED,
                                                                  MessageStatus.QUEUED, MessageStatus.MANUAL_PENDING]))):
        m.status = MessageStatus.SUPPRESSED
    cancel_followups(db, contact.id, reason)
    if org_status:
        contact.organization.status = org_status
    audit(db, actor, "contact.suppressed", "contact", contact.id, reason=reason)


# ------------------------------------------------------------------ approval

def approve(db: Session, msg: Message, actor: str, edited_body: str | None = None, edited_subject: str | None = None) -> Message:
    if msg.status not in (MessageStatus.DRAFTED,):
        raise DispatchBlocked(f"cannot approve a message in state {msg.status.value}")
    if edited_body is not None:
        msg.body = edited_body
    if edited_subject is not None:
        msg.subject = edited_subject
    msg.status, msg.approved_by, msg.approved_at = MessageStatus.APPROVED, actor, now_utc()
    if msg.contact_id:
        db.get(Contact, msg.contact_id).approved_for_contact = True
    org = db.get(Organization, msg.organization_id)
    if org.status == LeadStatus.MESSAGE_DRAFTED:
        org.status = LeadStatus.APPROVED
    audit(db, actor, "message.approved", "message", msg.id, edited=edited_body is not None)
    return msg


def reject(db: Session, msg: Message, actor: str, reason: str = "") -> None:
    msg.status = MessageStatus.REJECTED
    audit(db, actor, "message.rejected", "message", msg.id, reason=reason)


def auto_approve_allowed(db: Session, msg: Message) -> bool:
    """Bounded automation. Never for replies needing judgement, never without a verified contact."""
    policy = get_rule(db, "approval.policy")
    c = db.get(Contact, msg.contact_id) if msg.contact_id else None
    if not c or not c.verified or msg.kind in {"interested_reply", "rfp_interest"}:
        return False
    if policy == "approve_new_contact":
        return c.approved_for_contact and msg.kind.startswith("followup")
    if policy == "approved_segments":
        org = db.get(Organization, msg.organization_id)
        seg = f"{org.category}:{(org.country or '').upper()}"
        return msg.channel == "email" and seg in set(get_rule(db, "approval.segments") or [])
    return False


def try_auto_approve(db: Session, msg: Message) -> bool:
    if auto_approve_allowed(db, msg):
        msg.status, msg.approved_by, msg.approved_at = MessageStatus.APPROVED, "policy:" + get_rule(db, "approval.policy"), now_utc()
        audit(db, "policy", "message.auto_approved", "message", msg.id)
        return True
    return False


# ------------------------------------------------------------------ limits & time

def local_tz(db: Session, contact: Contact | None, org: Organization) -> ZoneInfo:
    tz = (contact.timezone if contact else None) or org.timezone
    return ZoneInfo(tz or COUNTRY_TZ.get((org.country or "").upper(), "UTC"))


def next_allowed_time(db: Session, at_utc: datetime, tz: ZoneInfo) -> datetime:
    """Push `at_utc` out of quiet hours/weekend in the recipient's zone."""
    qh = get_rule(db, "quiet_hours")
    t = at_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    weekend = {5, 6}  # Sat/Sun; the UAE moved to a Sat/Sun weekend in 2022
    for _ in range(14 * 24):
        in_quiet = t.hour >= qh["start"] or t.hour < qh["end"]
        if not in_quiet and t.weekday() not in weekend:
            return t.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        t = (t + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    return at_utc


def check_limits(db: Session, msg: Message) -> str | None:
    now = now_utc()
    lim = get_rule(db, f"limits.{msg.channel}") or {"per_hour": 0, "per_day": 0}
    base = select(func.count(Message.id)).where(Message.channel == msg.channel, Message.direction == "out",
                                                Message.status.in_(COUNTED))
    if db.scalar(base.where(Message.sent_at >= now - timedelta(hours=1))) >= lim["per_hour"]:
        return "hourly_limit"
    if db.scalar(base.where(Message.sent_at >= now - timedelta(days=1))) >= lim["per_day"]:
        return "daily_limit"
    if msg.contact_id:
        gap = get_rule(db, "limits.per_contact_days")
        recent = db.scalar(select(func.count(Message.id)).where(
            Message.contact_id == msg.contact_id, Message.direction == "out", Message.id != msg.id,
            Message.status.in_(COUNTED), Message.sent_at >= now - timedelta(days=gap)))
        if recent:
            return "contact_frequency"
    if msg.kind == "intro":
        gap = get_rule(db, "limits.per_company_days")
        recent = db.scalar(select(func.count(Message.id)).where(
            Message.organization_id == msg.organization_id, Message.direction == "out", Message.kind == "intro",
            Message.id != msg.id, Message.status.in_(COUNTED), Message.sent_at >= now - timedelta(days=gap)))
        if recent:
            return "company_frequency"
    return None


# ------------------------------------------------------------------ dispatch

def dispatch(db: Session, msg: Message, actor: str = "dispatcher") -> MessageStatus:
    """Attempt to send one approved message. Every exit path leaves an audit record."""
    h = halted(db)
    if h:
        audit(db, actor, "dispatch.halted", "message", msg.id, reason=h, level="warn")
        return msg.status
    if msg.status not in (MessageStatus.APPROVED, MessageStatus.QUEUED):
        raise DispatchBlocked(f"message {msg.id} is {msg.status.value}, not approved")
    if not msg.approved_by:
        raise DispatchBlocked("approval record missing")
    org = db.get(Organization, msg.organization_id)
    contact = db.get(Contact, msg.contact_id) if msg.contact_id else None
    reason = is_suppressed(db, contact)
    if reason:
        msg.status = MessageStatus.SUPPRESSED
        audit(db, actor, "dispatch.suppressed", "message", msg.id, reason=reason)
        return msg.status
    if msg.kind.startswith("followup") and contact and _has_inbound_since(db, contact.id, None):
        msg.status = MessageStatus.CANCELLED
        audit(db, actor, "dispatch.cancelled_replied", "message", msg.id)
        return msg.status
    drafts_mode = msg.channel == "email" and get_rule(db, "email.delivery") == "drafts" and hasattr(registry.email, "imap_host")
    lim = None if drafts_mode else check_limits(db, msg)
    if lim:
        msg.status, msg.scheduled_for = MessageStatus.QUEUED, now_utc() + timedelta(hours=1)
        audit(db, actor, "dispatch.deferred", "message", msg.id, reason=lim)
        return msg.status
    tz = local_tz(db, contact, org)
    allowed = now_utc() if drafts_mode else next_allowed_time(db, now_utc(), tz)
    if allowed > now_utc():
        msg.status, msg.scheduled_for = MessageStatus.QUEUED, allowed
        audit(db, actor, "dispatch.quiet_hours", "message", msg.id, until=allowed.isoformat())
        return msg.status
    msg.idempotency_key = msg.idempotency_key or f"msg-{msg.id}-{msg.content_hash[:16]}"

    if msg.channel == "linkedin":
        try:
            registry.linkedin.send_message(contact.linkedin_url, msg.body)
        except LinkedInActionBlocked as e:
            msg.status, msg.sent_at = MessageStatus.MANUAL_PENDING, now_utc()
            audit(db, actor, "linkedin.manual_required", "message", msg.id, reason=str(e), profile=contact.linkedin_url)
            _after_out(db, org, msg)
            return msg.status

    if msg.channel == "email" and get_rule(db, "email.delivery") == "drafts" and hasattr(registry.email, "imap_host"):
        p = profile(db)
        msg.attempts += 1
        try:
            draft_id = registry.email.create_draft(OutboundEmail(
                to=contact.email, subject=msg.subject or "", body=msg.body, from_addr=p.sender_email,
                idempotency_key=msg.idempotency_key))
        except SendError as e:
            msg.status, msg.last_error = MessageStatus.FAILED, str(e)[:500]
            audit(db, actor, "draft.failed", "message", msg.id, error=str(e), level="error")
            return msg.status
        # MANUAL_PENDING = waiting for Dheeraj to review and send it from Zoho; nothing has gone out yet.
        msg.status, msg.provider_message_id, msg.last_error = MessageStatus.MANUAL_PENDING, draft_id, None
        audit(db, actor, "draft.saved_to_mailbox", "message", msg.id, to=contact.email)
        return msg.status

    if not live_sending_enabled(db):
        msg.status, msg.sent_at = MessageStatus.DRY_RUN, now_utc()
        audit(db, actor, "dispatch.dry_run", "message", msg.id, to=contact.email if contact else None)
        _after_out(db, org, msg)
        return msg.status

    p = profile(db)
    thread = _thread(db, contact, msg.channel)
    msg.attempts += 1
    try:
        res = registry.email.send(OutboundEmail(
            to=contact.email, subject=msg.subject or "", body=msg.body, from_addr=p.sender_email,
            idempotency_key=msg.idempotency_key, thread_id=thread.provider_thread_id,
            list_unsubscribe=f"<mailto:{p.sender_email}?subject=unsubscribe>"))
    except SendError as e:
        msg.last_error = str(e)[:500]
        if e.permanent or msg.attempts >= MAX_ATTEMPTS:
            msg.status = MessageStatus.FAILED
            audit(db, actor, "dispatch.failed", "message", msg.id, error=str(e), level="error")
        else:
            msg.status = MessageStatus.QUEUED
            msg.scheduled_for = now_utc() + timedelta(minutes=2 ** msg.attempts * 5)
            audit(db, actor, "dispatch.retry", "message", msg.id, error=str(e), attempt=msg.attempts, level="warn")
        return msg.status
    except Exception as e:  # noqa: BLE001  unknown failures are failures, never successes
        msg.status, msg.last_error = MessageStatus.FAILED, str(e)[:500]
        audit(db, actor, "dispatch.failed", "message", msg.id, error=str(e), level="error")
        return msg.status
    if not res or not res.provider_message_id:
        msg.status = MessageStatus.FAILED
        audit(db, actor, "dispatch.failed", "message", msg.id, error="no provider id", level="error")
        return msg.status
    msg.status, msg.sent_at, msg.provider_message_id = MessageStatus.SENT, now_utc(), res.provider_message_id
    thread.provider_thread_id = thread.provider_thread_id or res.thread_id
    msg.thread_id = thread.id
    audit(db, actor, "dispatch.sent", "message", msg.id, provider_id=res.provider_message_id)
    _after_out(db, org, msg)
    return msg.status


def _thread(db: Session, contact: Contact, channel: str) -> Thread:
    t = db.scalar(select(Thread).where(Thread.contact_id == contact.id, Thread.channel == channel))
    if not t:
        t = Thread(contact_id=contact.id, channel=channel); db.add(t); db.flush()
    return t


def _after_out(db: Session, org: Organization, msg: Message) -> None:
    org.last_contact_at = msg.sent_at
    if org.status in {LeadStatus.APPROVED, LeadStatus.MESSAGE_DRAFTED, LeadStatus.QUALIFIED, LeadStatus.FOLLOW_UP_DUE}:
        org.status = LeadStatus.SENT
    if msg.kind == "intro" and msg.contact_id:
        schedule_followups(db, msg)


def confirm_manual_sent(db: Session, msg: Message, actor: str) -> None:
    if msg.status != MessageStatus.MANUAL_PENDING:
        raise DispatchBlocked("only MANUAL_PENDING messages can be confirmed as sent")
    msg.status, msg.sent_at = MessageStatus.SENT, now_utc()
    org = db.get(Organization, msg.organization_id)
    if msg.kind == "intro" and msg.channel == "email":
        _after_out(db, org, msg)  # follow-up clock starts when you actually send it
    audit(db, actor, "linkedin.manual_confirmed", "message", msg.id)


def mark_acknowledged(db: Session, msg: Message, actor: str) -> None:
    if msg.status != MessageStatus.SENT:
        raise DispatchBlocked("only SENT messages can be acknowledged")
    msg.status = MessageStatus.ACKNOWLEDGED
    audit(db, actor, "message.acknowledged", "message", msg.id)


# ------------------------------------------------------------------ follow-ups

def schedule_followups(db: Session, intro: Message) -> None:
    if not get_rule(db, "followup.enabled"):
        return
    base = intro.sent_at or now_utc()
    for step in get_rule(db, "followup.sequence") or []:
        key = f"fu-{intro.contact_id}-{intro.id}-{step['kind']}"
        if not db.scalar(select(Job).where(Job.dedupe_key == key)):
            db.add(Job(kind="followup", run_at=base + timedelta(days=step["day"]), dedupe_key=key,
                       payload={"intro_id": intro.id, "contact_id": intro.contact_id, "kind": step["kind"],
                                "channel": intro.channel}))


def cancel_followups(db: Session, contact_id: int, reason: str) -> int:
    n = 0
    for j in db.scalars(select(Job).where(Job.status == "PENDING", Job.kind == "followup")):
        if j.payload.get("contact_id") == contact_id:
            j.status, j.last_error = "CANCELLED", reason; n += 1
    for m in db.scalars(select(Message).where(Message.contact_id == contact_id, Message.kind.like("followup%"),
                                              Message.status.in_([MessageStatus.DRAFTED, MessageStatus.APPROVED,
                                                                  MessageStatus.QUEUED]))):
        m.status = MessageStatus.CANCELLED; n += 1
    return n


def _has_inbound_since(db: Session, contact_id: int, since: datetime | None) -> bool:
    q = select(func.count(Message.id)).where(Message.contact_id == contact_id, Message.direction == "in",
                                             Message.classification != "out_of_office")
    if since:
        q = q.where(Message.created_at >= since)
    return bool(db.scalar(q))


def run_followup_job(db: Session, job: Job) -> str:
    c = db.get(Contact, job.payload["contact_id"])
    org = c.organization
    if is_suppressed(db, c) or org.status in STOP_STATES | ENGAGED_STATES:
        return "skipped:stopped_or_engaged"
    if _has_inbound_since(db, c.id, None):
        return "skipped:replied"
    if not get_rule(db, "followup.enabled"):
        return "skipped:disabled"
    try:
        m = draft(db, org, c, kind=job.payload["kind"], channel=job.payload.get("channel", "email"))
    except GenerationBlocked as e:
        return f"skipped:{e}"
    org.status = LeadStatus.FOLLOW_UP_DUE
    org.next_followup_at = job.run_at
    if try_auto_approve(db, m):
        db.add(Job(kind="dispatch", run_at=now_utc(), payload={"message_id": m.id}, dedupe_key=f"dispatch-{m.id}"))
    return f"drafted:{m.id}"


# ------------------------------------------------------------------ replies

CLASS_RULES = [
    ("unsubscribe", r"\b(unsubscribe|remove me|stop (emailing|contacting)|do not (contact|email)|opt[ -]?out|take me off)\b"),
    ("out_of_office", r"\b(out of (the )?office|on (annual )?leave|away until|auto(matic)?[- ]reply|ooo)\b"),
    ("not_interested", r"\b(not interested|no thanks|no thank you|not (a )?fit|not looking|no requirement|no need)\b"),
    ("requesting_proposal", r"\b(proposal|quote|quotation|rate card|pricing|send (us|me) (your )?rates?)\b"),
    ("meeting", r"\b(meet|meeting|call|available (on|at)|calendar|schedule|slot|tuesday|wednesday|thursday|monday|friday)\b"),
    ("referral", r"\b(contact|reach out to|speak (to|with)|cc'?d|forwarding to|better person)\b"),
    ("requesting_info", r"\b(more (info|information|details)|can you share|cv|resume|profiles?|case stud)"),
    ("interested", r"\b(interested|sounds good|happy to|let'?s talk|keen|would like to)\b"),
]
ESCALATE = re.compile(r"(?i)\b(price|pricing|rate|rates|contract|nda|msa|legal|terms|exclusiv|payment|invoice|commit)")


def classify_reply(text: str) -> tuple[str, bool]:
    t = (text or "").lower()
    for label, pat in CLASS_RULES:
        if re.search(pat, t):
            return label, bool(ESCALATE.search(t)) or label in {"requesting_proposal", "referral"}
    return "ambiguous", True


def handle_inbound(db: Session, inbound: InboundEmail, actor: str = "inbox") -> Message | None:
    from .untrusted import clean_text, injection_suspected
    if db.scalar(select(Message).where(Message.provider_message_id == inbound.provider_message_id)):
        return None  # already processed
    addr = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", inbound.from_addr or "")
    body = clean_text(inbound.body, 8000)
    contact = None
    if inbound.is_bounce:
        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", body.replace(get_settings().admin_email, ""))
        contact = db.scalar(select(Contact).where(Contact.email == m.group(0).lower())) if m else None
        if contact:
            suppress(db, contact, "bounce", actor, LeadStatus.BOUNCED)
            for om in db.scalars(select(Message).where(Message.contact_id == contact.id, Message.status == MessageStatus.SENT)):
                om.status = MessageStatus.BOUNCED
        audit(db, actor, "email.bounce", "contact", contact.id if contact else None)
        return None
    if addr:
        contact = db.scalar(select(Contact).where(Contact.email == addr.group(0).lower()))
    if not contact:
        audit(db, actor, "email.unmatched_inbound", detail_from=inbound.from_addr[:120])
        return None
    label, escalate = classify_reply(body)
    if inbound.auto_submitted and label != "unsubscribe":
        label, escalate = "out_of_office", False
    msg = Message(organization_id=contact.organization_id, contact_id=contact.id, direction="in", channel="email",
                  kind="reply", subject=inbound.subject[:255], body=body, status=MessageStatus.ACKNOWLEDGED,
                  provider_message_id=inbound.provider_message_id, classification=label)
    db.add(msg); db.flush()
    if injection_suspected(body):
        escalate = True
        audit(db, actor, "untrusted.injection_suspected", "message", msg.id, level="warn")
    org = contact.organization
    t = _thread(db, contact, "email")
    t.last_classification = label
    if label == "unsubscribe":
        suppress(db, contact, "opt_out", actor, LeadStatus.UNSUBSCRIBED)
    elif label == "not_interested":
        suppress(db, contact, "not_interested", actor, LeadStatus.NOT_INTERESTED)
    elif label == "out_of_office":
        pass  # sequence continues; follow-ups already respect spacing
    else:
        cancel_followups(db, contact.id, f"reply:{label}")
        t.state = "ACTIVE_DISCUSSION"
        org.status = LeadStatus.NEEDS_REVIEW if escalate else LeadStatus.REPLIED
        org.next_action = f"Reply classified '{label}'" + (" — needs human review" if escalate else "")
    audit(db, actor, "email.reply", "message", msg.id, classification=label, escalate=escalate)
    return msg


def poll_inbox(db: Session) -> int:
    n = 0
    for ib in registry.email.fetch_replies():
        if handle_inbound(db, ib):
            n += 1
    db.commit()
    return n


# ------------------------------------------------------------------ job worker

def enqueue_dispatch(db: Session, msg: Message) -> Job:
    key = f"dispatch-{msg.id}"
    j = db.scalar(select(Job).where(Job.dedupe_key == key))
    if j and j.status in ("PENDING",):
        return j
    if j:
        j.status, j.run_at = "PENDING", msg.scheduled_for or now_utc()
        return j
    j = Job(kind="dispatch", run_at=msg.scheduled_for or now_utc(), payload={"message_id": msg.id}, dedupe_key=key)
    db.add(j)
    return j


def run_due_jobs(db: Session, limit: int = 50) -> dict:
    stats = {"ran": 0, "failed": 0, "halted": 0}
    jobs = list(db.scalars(select(Job).where(Job.status == "PENDING", Job.run_at <= now_utc())
                           .order_by(Job.run_at).limit(limit)))
    for j in jobs:
        if halted(db) and j.kind in ("dispatch", "followup"):
            stats["halted"] += 1
            continue
        j.attempts += 1
        try:
            if j.kind == "dispatch":
                m = db.get(Message, j.payload["message_id"])
                st = dispatch(db, m)
                if st == MessageStatus.QUEUED:
                    j.run_at = m.scheduled_for; j.status = "PENDING"
                    if j.attempts >= j.max_attempts * 3:
                        j.status = "DEAD"
                    db.commit(); continue
                j.last_error = None if st in (MessageStatus.SENT, MessageStatus.DRY_RUN, MessageStatus.MANUAL_PENDING) else st.value
            elif j.kind == "followup":
                j.last_error = run_followup_job(db, j)
            elif j.kind == "reminder":
                from .scheduling import send_reminder
                j.last_error = send_reminder(db, j.payload["appointment_id"])
            j.status = "DONE"; stats["ran"] += 1
        except Exception as e:  # noqa: BLE001
            db.rollback()
            j = db.get(Job, j.id)
            j.attempts = (j.attempts or 0) + 1
            j.last_error = str(e)[:500]
            j.status = "DEAD" if j.attempts >= j.max_attempts else "PENDING"
            j.run_at = now_utc() + timedelta(minutes=2 ** j.attempts)
            audit(db, "worker", "job.error", "job", j.id, error=str(e), level="error")
            stats["failed"] += 1
        db.commit()
    # re-enqueue deferred messages
    for m in db.scalars(select(Message).where(Message.status == MessageStatus.QUEUED,
                                              or_(Message.scheduled_for.is_(None), Message.scheduled_for <= now_utc()))):
        if not halted(db):
            enqueue_dispatch(db, m)
    db.commit()
    return stats
