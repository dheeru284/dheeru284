"""Structural and integrity checks on a candle series.

These run on every series before indicators or the strategy see it. They
re-check per-candle integrity even though :class:`Candle` validates on
construction, because adapters may build models with ``model_construct`` for
speed, and a bad bar must surface as ``DATA_INVALID`` rather than a bad signal.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel

from .schemas import Candle, CandleSeries
from .session import IST, bar_starts, is_aligned, is_market_open


class IssueCode(str, Enum):
    EMPTY = "EMPTY"
    NAIVE_TIMESTAMP = "NAIVE_TIMESTAMP"
    BAD_PRICE = "BAD_PRICE"
    OHLC_INCONSISTENT = "OHLC_INCONSISTENT"
    NEGATIVE_VOLUME = "NEGATIVE_VOLUME"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    DUPLICATE = "DUPLICATE"
    MISALIGNED = "MISALIGNED"
    GAP = "GAP"
    INCOMPLETE_SESSION = "INCOMPLETE_SESSION"
    FUTURE_CANDLE = "FUTURE_CANDLE"
    STALE = "STALE"


class DataIssue(BaseModel):
    code: IssueCode
    message: str
    timestamp: datetime | None = None


def _price_ok(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def _candle_issues(candle: Candle) -> list[DataIssue]:
    ts = candle.timestamp
    if ts.tzinfo is None or ts.utcoffset() is None:
        return [DataIssue(code=IssueCode.NAIVE_TIMESTAMP, message="timestamp has no timezone")]
    prices = (candle.open, candle.high, candle.low, candle.close)
    if not all(_price_ok(p) for p in prices):
        return [DataIssue(code=IssueCode.BAD_PRICE, message=f"non-positive or non-finite price {prices}", timestamp=ts)]
    issues = []
    if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
        issues.append(DataIssue(code=IssueCode.OHLC_INCONSISTENT, message=f"high/low do not bound open/close {prices}", timestamp=ts))
    if candle.volume < 0:
        issues.append(DataIssue(code=IssueCode.NEGATIVE_VOLUME, message=f"volume {candle.volume}", timestamp=ts))
    return issues


def validate_series(
    series: CandleSeries,
    as_of: datetime | None = None,
    max_staleness_bars: int = 2,
) -> list[DataIssue]:
    """Return every problem found; an empty list means the series is usable.

    ``as_of`` enables the freshness checks: no candle may end after ``as_of``,
    and while the market is open the latest candle must have closed within
    ``max_staleness_bars`` intervals.
    """
    candles = series.candles
    interval = series.interval
    if not candles:
        return [DataIssue(code=IssueCode.EMPTY, message="series has no candles")]

    issues = [issue for candle in candles for issue in _candle_issues(candle)]
    if any(i.code is IssueCode.NAIVE_TIMESTAMP for i in issues):
        return issues  # ordering checks are meaningless without a timezone

    for prev, cur in zip(candles, candles[1:]):
        if cur.timestamp == prev.timestamp:
            issues.append(DataIssue(code=IssueCode.DUPLICATE, message="duplicate candle", timestamp=cur.timestamp))
        elif cur.timestamp < prev.timestamp:
            issues.append(DataIssue(code=IssueCode.OUT_OF_ORDER, message="candle earlier than its predecessor", timestamp=cur.timestamp))

    for candle in candles:
        if not is_aligned(candle.timestamp, interval):
            issues.append(DataIssue(code=IssueCode.MISALIGNED, message=f"not a {interval.value} bar start inside the session", timestamp=candle.timestamp))

    if issues:
        return issues  # gap analysis assumes ordered, aligned, unique bars

    by_day: dict[date, list[datetime]] = defaultdict(list)
    for candle in candles:
        by_day[candle.timestamp.astimezone(IST).date()].append(candle.timestamp)
    days = sorted(by_day)
    for day in days:
        expected = bar_starts(day, interval)
        got = by_day[day]
        is_last_day = day == days[-1]
        # The first day may start mid-session (the request window cut it), and
        # the last day may be in progress. Inside the run, bars must be contiguous.
        first = expected.index(got[0])
        run = expected[first : first + len(got)]
        if got != run:
            missing = next(e for e, g in zip(run, got) if e != g)
            issues.append(DataIssue(code=IssueCode.GAP, message="missing candle inside session", timestamp=missing))
        elif day != days[0] and first != 0:
            issues.append(DataIssue(code=IssueCode.GAP, message="session is missing its opening candles", timestamp=expected[0]))
        elif not is_last_day and first + len(got) != len(expected):
            issues.append(DataIssue(code=IssueCode.INCOMPLETE_SESSION, message=f"session {day} ends early", timestamp=got[-1]))

    if as_of is not None:
        last_end = candles[-1].timestamp + interval.delta
        if last_end > as_of:
            issues.append(DataIssue(code=IssueCode.FUTURE_CANDLE, message="latest candle has not closed yet at as_of", timestamp=candles[-1].timestamp))
        elif is_market_open(as_of) and as_of - last_end > interval.delta * max_staleness_bars:
            issues.append(DataIssue(code=IssueCode.STALE, message=f"latest candle closed {as_of - last_end} before as_of", timestamp=candles[-1].timestamp))

    return issues
