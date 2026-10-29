from datetime import date, datetime

from optionpulse.schemas import Interval
from optionpulse.session import (
    IST, bar_starts, is_aligned, is_market_open, latest_session_day, previous_trading_days,
)


def test_bar_counts():
    day = date(2026, 10, 28)
    assert len(bar_starts(day, Interval.FIVE_MINUTE)) == 75
    assert len(bar_starts(day, Interval.ONE_MINUTE)) == 375
    bars = bar_starts(day, Interval.FIVE_MINUTE)
    assert bars[0] == datetime(2026, 10, 28, 9, 15, tzinfo=IST)
    assert bars[-1] == datetime(2026, 10, 28, 15, 25, tzinfo=IST)


def test_alignment():
    assert is_aligned(datetime(2026, 10, 28, 9, 20, tzinfo=IST), Interval.FIVE_MINUTE)
    assert not is_aligned(datetime(2026, 10, 28, 9, 21, tzinfo=IST), Interval.FIVE_MINUTE)
    assert not is_aligned(datetime(2026, 10, 28, 15, 30, tzinfo=IST), Interval.FIVE_MINUTE)
    assert not is_aligned(datetime(2026, 10, 28, 9, 10, tzinfo=IST), Interval.FIVE_MINUTE)


def test_market_hours_and_weekends():
    assert is_market_open(datetime(2026, 10, 28, 9, 15, tzinfo=IST))
    assert not is_market_open(datetime(2026, 10, 28, 15, 30, tzinfo=IST))
    assert not is_market_open(datetime(2026, 10, 31, 11, 0, tzinfo=IST))  # Saturday


def test_session_day_resolution():
    assert latest_session_day(datetime(2026, 10, 28, 9, 0, tzinfo=IST)) == date(2026, 10, 27)
    assert latest_session_day(datetime(2026, 10, 28, 9, 15, tzinfo=IST)) == date(2026, 10, 28)
    assert latest_session_day(datetime(2026, 11, 1, 12, 0, tzinfo=IST)) == date(2026, 10, 30)  # Sunday
    assert previous_trading_days(date(2026, 11, 2), 3) == [date(2026, 10, 29), date(2026, 10, 30), date(2026, 11, 2)]
