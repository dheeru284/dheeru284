import hashlib
from datetime import date, datetime

import pytest

from optionpulse.providers import MockMarketDataProvider, UnknownInstrument, UnsupportedInterval
from optionpulse.schemas import DataSource, Interval
from optionpulse.session import IST, session_bounds
from optionpulse.validation import validate_series

DAY = date(2026, 10, 28)
OPEN, CLOSE = session_bounds(DAY)


def fingerprint(series) -> str:
    rows = "|".join(f"{c.timestamp.isoformat()},{c.open},{c.high},{c.low},{c.close},{c.volume}" for c in series.candles)
    return hashlib.sha256(rows.encode()).hexdigest()


def test_full_session_is_valid_and_labelled_simulated():
    s = MockMarketDataProvider().get_candles("NIFTY", Interval.FIVE_MINUTE, OPEN, CLOSE)
    assert s.source is DataSource.SIMULATED
    assert len(s.candles) == 75
    assert validate_series(s) == []
    assert all(round(c.close / 0.05, 6).is_integer() for c in s.candles)


def test_deterministic_across_instances():
    a = MockMarketDataProvider(seed=7).get_candles("NIFTY", Interval.FIVE_MINUTE, OPEN, CLOSE)
    b = MockMarketDataProvider(seed=7).get_candles("NIFTY", Interval.FIVE_MINUTE, OPEN, CLOSE)
    assert a == b
    c = MockMarketDataProvider(seed=8).get_candles("NIFTY", Interval.FIVE_MINUTE, OPEN, CLOSE)
    assert a.candles != c.candles


def test_golden_fingerprint():
    """Pins the generator. If this changes, simulated history changed for every user."""
    s = MockMarketDataProvider(seed=7).get_candles("NIFTY", Interval.FIVE_MINUTE, OPEN, CLOSE)
    assert fingerprint(s) == GOLDEN


GOLDEN = "4d8c91704d95b1bb5ee9942984203797c0e8bb90bfd00fa0cefbec8406569087"


def test_window_independent():
    p = MockMarketDataProvider()
    wide = p.get_candles("NIFTY", Interval.FIVE_MINUTE, session_bounds(date(2026, 10, 26))[0], CLOSE)
    narrow = p.get_candles("NIFTY", Interval.FIVE_MINUTE, OPEN, CLOSE)
    assert wide.candles[-75:] == narrow.candles


def test_intervals_aggregate_consistently():
    p = MockMarketDataProvider()
    ones = p.get_candles("NIFTY", Interval.ONE_MINUTE, OPEN, CLOSE).candles
    fives = p.get_candles("NIFTY", Interval.FIVE_MINUTE, OPEN, CLOSE).candles
    assert len(ones) == 375
    for i, bar in enumerate(fives):
        chunk = ones[i * 5 : i * 5 + 5]
        assert bar.open == chunk[0].open and bar.close == chunk[-1].close
        assert bar.high == max(c.high for c in chunk) and bar.low == min(c.low for c in chunk)
        assert bar.volume == sum(c.volume for c in chunk)


def test_only_completed_candles_returned():
    at = datetime(2026, 10, 28, 10, 7, tzinfo=IST)
    s = MockMarketDataProvider().get_candles("NIFTY", Interval.FIVE_MINUTE, OPEN, at)
    assert s.candles[-1].timestamp == datetime(2026, 10, 28, 10, 0, tzinfo=IST)
    assert len(s.candles) == 10


def test_weekend_has_no_candles():
    sat = session_bounds(date(2026, 10, 31))
    assert MockMarketDataProvider().get_candles("NIFTY", Interval.FIVE_MINUTE, *sat).candles == []


def test_errors():
    p = MockMarketDataProvider()
    with pytest.raises(UnknownInstrument):
        p.get_candles("RELIANCE", Interval.FIVE_MINUTE, OPEN, CLOSE)
    with pytest.raises(UnsupportedInterval):
        p.get_candles("NIFTY", Interval.TEN_MINUTE, OPEN, CLOSE)
    with pytest.raises(ValueError):
        p.get_candles("NIFTY", Interval.FIVE_MINUTE, OPEN.replace(tzinfo=None), CLOSE)


def test_instrument_lookup_is_case_insensitive():
    assert MockMarketDataProvider().get_instrument("nifty").display_name == "NIFTY 50"
