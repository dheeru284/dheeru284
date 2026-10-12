"""Appointment scheduling: slot proposals, conflict checks, confirmation, reminders, outcomes."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .core import audit, get_rule, now_utc
from .models import Appointment, CalendarEvent, Contact, Job, LeadStatus, Organization
from .providers import registry

UTC = ZoneInfo("UTC")


class SchedulingError(Exception):
    pass


def to_utc(local: datetime, tz: str) -> datetime:
    return local.replace(tzinfo=ZoneInfo(tz)).astimezone(UTC).replace(tzinfo=None)


def to_local(utc: datetime, tz: str) -> datetime:
    return utc.replace(tzinfo=UTC).astimezone(ZoneInfo(tz))


def _busy(db: Session, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    out = [(e.start_utc, e.end_utc) for e in db.scalars(select(CalendarEvent).where(
        CalendarEvent.start_utc < end, CalendarEvent.end_utc > start))]
    out += [(a.start_utc, a.end_utc) for a in db.scalars(select(Appointment).where(
        Appointment.status.in_(["CONFIRMED", "RESCHEDULED"]), Appointment.start_utc < end, Appointment.end_utc > start))]
    if registry.calendar.connected:
        out += [(b.start_utc, b.end_utc) for b in registry.calendar.busy(start, end)]
    return out


def conflicts(db: Session, start: datetime, end: datetime, buffer_min: int = 0, exclude_appt: int | None = None) -> bool:
    s, e = start - timedelta(minutes=buffer_min), end + timedelta(minutes=buffer_min)
    for bs, be in _busy(db, s, e):
        if exclude_appt:
            a = db.get(Appointment, exclude_appt)
            if a and a.start_utc == bs and a.end_utc == be:
                continue
        if bs < e and be > s:
            return True
    return False


def availability_status(db: Session) -> tuple[bool, str]:
    if registry.calendar.connected:
        return True, "calendar"
    av = get_rule(db, "availability")
    return bool(av.get("confirmed_by_admin")), "configured_window"


def propose_slots(db: Session, *, fmt: str = "remote", n: int = 3, start_date: date | None = None,
                  end_date: date | None = None, tz: str | None = None) -> list[datetime]:
    av = get_rule(db, "availability")
    tz = tz or av["timezone"]
    dur, buf = av["meeting_minutes"], av["buffer_minutes"]
    today_local = to_local(now_utc(), tz).date()
    if fmt == "in_person":
        cfg = get_rule(db, "campaign.dubai")
        start_date = max(start_date or date.fromisoformat(cfg["window_start"]), today_local + timedelta(days=1))
        end_date = end_date or date.fromisoformat(cfg["window_end"])
        tz = "Asia/Dubai"
        if start_date > end_date:
            raise SchedulingError("The Dubai meeting window has passed; propose remote meetings instead.")
    start_date = start_date or today_local + timedelta(days=2)
    end_date = end_date or start_date + timedelta(days=14)
    slots: list[datetime] = []
    d = start_date
    while d <= end_date and len(slots) < n:
        if d.weekday() in av["days"]:
            t = datetime.combine(d, time(av["start_hour"]))
            while t.hour < av["end_hour"] and len(slots) < n:
                s = to_utc(t, tz); e = s + timedelta(minutes=dur)
                if to_local(e, tz).hour <= av["end_hour"] and s > now_utc() and not conflicts(db, s, e, buf) \
                        and all(abs((s - x).total_seconds()) >= 3 * 3600 for x in slots):
                    slots.append(s)
                t += timedelta(minutes=30)
        d += timedelta(days=1)
    return slots


def create_proposal(db: Session, org: Organization, contact: Contact | None, fmt: str, actor: str,
                    campaign_id: int | None = None) -> Appointment:
    ok, src = availability_status(db)
    slots = propose_slots(db, fmt=fmt)
    if not slots:
        raise SchedulingError("No free slots in the configured window.")
    a = Appointment(organization_id=org.id, contact_id=contact.id if contact else None, campaign_id=campaign_id,
                    format=fmt, proposed_slots=[s.isoformat() for s in slots],
                    timezone="Asia/Dubai" if fmt == "in_person" else get_rule(db, "availability")["timezone"],
                    next_action=None if ok else "Availability not confirmed — confirm before sending slots.")
    db.add(a); db.flush()
    org.status = LeadStatus.MEETING_PROPOSED
    audit(db, actor, "appointment.proposed", "appointment", a.id, availability_source=src, confirmed=ok)
    return a


def confirm(db: Session, appt: Appointment, slot_utc: datetime, actor: str, *, prospect_agreed: bool,
            location: str | None = None, meeting_link: str | None = None, attendee_email: str | None = None) -> Appointment:
    """Book only after the prospect agreed to the slot. In-person needs a prospect-confirmed location."""
    if not prospect_agreed:
        raise SchedulingError("Prospect has not agreed to this slot; not booking.")
    ok, _ = availability_status(db)
    if not ok:
        raise SchedulingError("Availability is not confirmed (no calendar connected and window not confirmed).")
    av = get_rule(db, "availability")
    end = slot_utc + timedelta(minutes=av["meeting_minutes"])
    if conflicts(db, slot_utc, end, av["buffer_minutes"], exclude_appt=appt.id):
        raise SchedulingError("Slot conflicts with an existing commitment.")
    if appt.format == "in_person" and not location:
        raise SchedulingError("In-person meeting needs a location confirmed by the prospect.")
    org = db.get(Organization, appt.organization_id)
    appt.start_utc, appt.end_utc = slot_utc, end
    appt.location, appt.location_confirmed = location, bool(location)
    appt.meeting_link = meeting_link
    appt.agenda = appt.agenda or default_agenda(db, org)
    try:
        from .integrations.calendar import NewEvent
        eid = registry.calendar.create_event(NewEvent(
            title=f"{org.name} / EpohTech", start_utc=slot_utc, end_utc=end, timezone=appt.timezone,
            attendees=[attendee_email] if attendee_email else [], location=location or meeting_link,
            description=appt.agenda))
    except Exception as e:  # noqa: BLE001
        audit(db, actor, "appointment.calendar_failed", "appointment", appt.id, error=str(e), level="error")
        raise SchedulingError(f"Calendar event could not be created: {e}") from e
    appt.calendar_event_id = eid
    appt.status = "CONFIRMED"
    db.add(CalendarEvent(provider_event_id=eid, title=f"Meeting: {org.name}", start_utc=slot_utc, end_utc=end,
                         appointment_id=appt.id))
    org.status = LeadStatus.MEETING_BOOKED
    org.next_action = f"Meeting {to_local(slot_utc, appt.timezone):%a %d %b %H:%M} {appt.timezone}"
    for hrs in (24, 2):
        at = slot_utc - timedelta(hours=hrs)
        if at > now_utc():
            db.add(Job(kind="reminder", run_at=at, payload={"appointment_id": appt.id},
                       dedupe_key=f"rem-{appt.id}-{hrs}-{slot_utc.isoformat()}"))
    audit(db, actor, "appointment.confirmed", "appointment", appt.id, start_utc=slot_utc.isoformat(),
          tz=appt.timezone, format=appt.format)
    return appt


def cancel(db: Session, appt: Appointment, actor: str, reason: str = "") -> None:
    if appt.calendar_event_id:
        registry.calendar.cancel_event(appt.calendar_event_id)
        ev = db.scalar(select(CalendarEvent).where(CalendarEvent.provider_event_id == appt.calendar_event_id))
        if ev:
            db.delete(ev)
    for j in db.scalars(select(Job).where(Job.kind == "reminder", Job.status == "PENDING")):
        if j.payload.get("appointment_id") == appt.id:
            j.status = "CANCELLED"
    appt.status = "CANCELLED"
    audit(db, actor, "appointment.cancelled", "appointment", appt.id, reason=reason)


def reschedule(db: Session, appt: Appointment, new_slot: datetime, actor: str, **kw) -> Appointment:
    old = appt.start_utc
    cancel(db, appt, actor, "reschedule")
    appt.status = "PROPOSED"; appt.calendar_event_id = None
    confirm(db, appt, new_slot, actor, prospect_agreed=True, location=kw.get("location", appt.location),
            meeting_link=kw.get("meeting_link", appt.meeting_link), attendee_email=kw.get("attendee_email"))
    appt.status = "RESCHEDULED"
    audit(db, actor, "appointment.rescheduled", "appointment", appt.id, old=old.isoformat() if old else None)
    return appt


def record_outcome(db: Session, appt: Appointment, actor: str, attended: bool, outcome: str, next_action: str) -> None:
    appt.attended, appt.outcome, appt.next_action = attended, outcome, next_action
    appt.status = "COMPLETED" if attended else "NO_SHOW"
    org = db.get(Organization, appt.organization_id)
    if attended:
        org.status = LeadStatus.COMPLETED
    org.next_action = next_action
    audit(db, actor, "appointment.outcome", "appointment", appt.id, attended=attended)


def default_agenda(db: Session, org: Organization) -> str:
    ev = next((e for e in org.evidence if not e.is_inference), None)
    lines = ["1. Introductions (5 min)",
             f"2. {org.name}'s current and upcoming requirements" + (f" — incl. {ev.summary[:80]}" if ev else ""),
             "3. EpohTech services and engagement models (contract, subcontract, remote/offshore)",
             "4. Next steps (vendor onboarding, profiles, follow-up)"]
    return "\n".join(lines)


def send_reminder(db: Session, appointment_id: int) -> str:
    from .messaging import GenerationBlocked, draft
    from .outreach import try_auto_approve
    a = db.get(Appointment, appointment_id)
    if not a or a.status not in ("CONFIRMED", "RESCHEDULED"):
        return "skipped"
    c = db.get(Contact, a.contact_id) if a.contact_id else None
    try:
        m = draft(db, db.get(Organization, a.organization_id), c, kind="meeting_reminder",
                  extra=meeting_ctx(a))
    except GenerationBlocked as e:
        return f"skipped:{e}"
    try_auto_approve(db, m)
    return f"drafted:{m.id}"


def meeting_ctx(a: Appointment) -> dict:
    lt = to_local(a.start_utc, a.timezone) if a.start_utc else None
    ist = to_local(a.start_utc, "Asia/Kolkata") if a.start_utc else None
    return {"meeting_time": f"{lt:%A %d %B %Y, %H:%M} ({a.timezone}) / {ist:%H:%M} IST" if lt else "TBC",
            "meeting_format": "In person" if a.format == "in_person" else "Video call",
            "meeting_location": (f"Location: {a.location}" if a.location else (f"Link: {a.meeting_link}" if a.meeting_link else "")),
            "agenda": a.agenda or "", "next_action": a.next_action or ""}
