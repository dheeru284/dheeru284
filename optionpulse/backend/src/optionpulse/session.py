"""NSE cash/F&O session calendar (regular session only).

The exchange holiday list is not modelled yet: every weekday is treated as a
trading day. Phase 3 should load NSE's published holiday calendar.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from .schemas import Interval

IST = timezone(timedelta(hours=5, minutes=30), name="IST")
SESSION_OPEN = time(9, 15)
SESSION_CLOSE = time(15, 30)


def is_trading_day(day: date) -> bool:
    return day.weekday() < 5


def session_bounds(day: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(day, SESSION_OPEN, tzinfo=IST),
        datetime.combine(day, SESSION_CLOSE, tzinfo=IST),
    )


def bar_starts(day: date, interval: Interval) -> list[datetime]:
    """Start times of every full bar in the session, e.g. 75 five-minute bars."""
    start, end = session_bounds(day)
    bars = []
    current = start
    while current + interval.delta <= end:
        bars.append(current)
        current += interval.delta
    return bars


def is_aligned(ts: datetime, interval: Interval) -> bool:
    """True if ``ts`` is a bar start inside the session for ``interval``."""
    local = ts.astimezone(IST)
    start, end = session_bounds(local.date())
    if not (start <= local and local + interval.delta <= end):
        return False
    offset = local - start
    return offset.seconds % (interval.minutes * 60) == 0 and offset.microseconds == 0


def is_market_open(at: datetime) -> bool:
    local = at.astimezone(IST)
    start, end = session_bounds(local.date())
    return is_trading_day(local.date()) and start <= local < end


def previous_trading_days(end: date, count: int) -> list[date]:
    """The ``count`` trading days ending on or before ``end``, oldest first."""
    days: list[date] = []
    current = end
    while len(days) < count:
        if is_trading_day(current):
            days.append(current)
        current -= timedelta(days=1)
    return list(reversed(days))


def latest_session_day(at: datetime) -> date:
    """The session that is live at ``at``, or the most recent one that has opened."""
    local = at.astimezone(IST)
    day = local.date()
    if is_trading_day(day) and local >= session_bounds(day)[0]:
        return day
    return previous_trading_days(day - timedelta(days=1), 1)[0]
