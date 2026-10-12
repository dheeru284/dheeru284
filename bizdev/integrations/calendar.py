"""Calendar provider adapters. Times are naive UTC at this boundary."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

import httpx


@dataclass
class Busy:
    start_utc: datetime
    end_utc: datetime


@dataclass
class NewEvent:
    title: str
    start_utc: datetime
    end_utc: datetime
    timezone: str
    attendees: list[str]
    location: str | None
    description: str


class CalendarProvider(Protocol):
    name: str
    connected: bool
    def busy(self, start_utc: datetime, end_utc: datetime) -> list[Busy]: ...
    def create_event(self, ev: NewEvent) -> str: ...
    def cancel_event(self, event_id: str) -> None: ...


@dataclass
class MockCalendar:
    name: str = "mock"
    connected: bool = False  # mock == no real calendar; availability must be confirmed by admin
    events: dict = field(default_factory=dict)
    fail: bool = False

    def busy(self, start_utc, end_utc):
        return [Busy(e.start_utc, e.end_utc) for e in self.events.values()
                if e.start_utc < end_utc and e.end_utc > start_utc]

    def create_event(self, ev: NewEvent) -> str:
        if self.fail:
            raise RuntimeError("calendar unavailable")
        eid = f"mock-ev-{uuid.uuid4().hex[:8]}"
        self.events[eid] = ev
        return eid

    def cancel_event(self, event_id: str) -> None:
        self.events.pop(event_id, None)


class GoogleCalendar:
    """Scopes: calendar.freebusy (read busy) + calendar.events (create invites). Not verified live."""
    name = "gcal"
    connected = True
    SCOPES = ["https://www.googleapis.com/auth/calendar.freebusy",
              "https://www.googleapis.com/auth/calendar.events"]
    BASE = "https://www.googleapis.com/calendar/v3"

    def __init__(self, token_getter, calendar_id: str = "primary", client: httpx.Client | None = None):
        self._tok, self.cal, self.client = token_getter, calendar_id, client or httpx.Client(timeout=30)

    def _h(self):
        return {"Authorization": f"Bearer {self._tok()}"}

    @staticmethod
    def _iso(d: datetime) -> str:
        return d.replace(tzinfo=timezone.utc).isoformat()

    def busy(self, start_utc, end_utc):
        r = self.client.post(f"{self.BASE}/freeBusy", headers=self._h(), json={
            "timeMin": self._iso(start_utc), "timeMax": self._iso(end_utc), "items": [{"id": self.cal}]})
        r.raise_for_status()
        out = []
        for b in r.json()["calendars"][self.cal]["busy"]:
            s = datetime.fromisoformat(b["start"].replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
            e = datetime.fromisoformat(b["end"].replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
            out.append(Busy(s, e))
        return out

    def create_event(self, ev: NewEvent) -> str:
        r = self.client.post(f"{self.BASE}/calendars/{self.cal}/events", headers=self._h(),
                             params={"sendUpdates": "all"}, json={
            "summary": ev.title, "description": ev.description, "location": ev.location,
            "start": {"dateTime": self._iso(ev.start_utc), "timeZone": ev.timezone},
            "end": {"dateTime": self._iso(ev.end_utc), "timeZone": ev.timezone},
            "attendees": [{"email": a} for a in ev.attendees]})
        r.raise_for_status()
        return r.json()["id"]

    def cancel_event(self, event_id: str) -> None:
        self.client.delete(f"{self.BASE}/calendars/{self.cal}/events/{event_id}", headers=self._h(),
                           params={"sendUpdates": "all"}).raise_for_status()
