from datetime import date, datetime, timedelta

from optionpulse.schemas import Candle
from optionpulse.session import IST, bar_starts
from optionpulse.schemas import Interval
from optionpulse.validation import IssueCode, validate_series

from .conftest import make_series, zigzag


def codes(series, **kw):
    return {i.code for i in validate_series(series, **kw)}


def with_candles(series, candles):
    return series.model_copy(update={"candles": candles})


def test_clean_series_has_no_issues():
    assert validate_series(make_series(zigzag(100, 2, 1, 40))) == []


def test_empty():
    s = make_series([100.0])
    assert codes(with_candles(s, [])) == {IssueCode.EMPTY}


def test_gap_inside_session():
    s = make_series(zigzag(100, 2, 1, 10))
    assert codes(with_candles(s, s.candles[:4] + s.candles[5:])) == {IssueCode.GAP}


def test_duplicate_and_out_of_order():
    s = make_series(zigzag(100, 2, 1, 5))
    c = s.candles
    assert IssueCode.DUPLICATE in codes(with_candles(s, c[:3] + [c[2]] + c[3:]))
    assert IssueCode.OUT_OF_ORDER in codes(with_candles(s, [c[0], c[2], c[1], c[3]]))


def test_misaligned_bar():
    s = make_series([100.0, 101.0])
    shifted = s.candles[1].model_copy(update={"timestamp": s.candles[1].timestamp + timedelta(minutes=2)})
    assert codes(with_candles(s, [s.candles[0], shifted])) == {IssueCode.MISALIGNED}


def test_integrity_rechecked_for_unvalidated_candles():
    s = make_series([100.0, 101.0])
    ts = s.candles[1].timestamp
    broken = Candle.model_construct(timestamp=ts, open=101.0, high=100.0, low=99.0, close=101.0, volume=5)
    assert codes(with_candles(s, [s.candles[0], broken])) == {IssueCode.OHLC_INCONSISTENT}
    nan = Candle.model_construct(timestamp=ts, open=101.0, high=float("nan"), low=99.0, close=101.0, volume=5)
    assert codes(with_candles(s, [s.candles[0], nan])) == {IssueCode.BAD_PRICE}
    naive = Candle.model_construct(timestamp=ts.replace(tzinfo=None), open=1.0, high=1.0, low=1.0, close=1.0, volume=0)
    assert codes(with_candles(s, [naive])) == {IssueCode.NAIVE_TIMESTAMP}


def test_previous_session_must_be_complete_and_later_sessions_start_at_open():
    prev = make_series(zigzag(100, 2, 1, 75), day=date(2026, 10, 27))
    today = make_series(zigzag(150, 2, 1, 10), day=date(2026, 10, 28))
    assert validate_series(with_candles(prev, prev.candles + today.candles)) == []
    assert codes(with_candles(prev, prev.candles[:-1] + today.candles)) == {IssueCode.INCOMPLETE_SESSION}
    assert codes(with_candles(prev, prev.candles + today.candles[2:])) == {IssueCode.GAP}
    # The first day may begin mid-session because the request window cut it.
    assert validate_series(with_candles(prev, prev.candles[30:] + today.candles)) == []


def test_freshness_against_as_of():
    s = make_series(zigzag(100, 2, 1, 10))  # last candle 10:00-10:05
    last_end = s.candles[-1].timestamp + Interval.FIVE_MINUTE.delta
    assert validate_series(s, as_of=last_end) == []
    assert codes(s, as_of=last_end - timedelta(minutes=1)) == {IssueCode.FUTURE_CANDLE}
    assert codes(s, as_of=last_end + timedelta(minutes=11)) == {IssueCode.STALE}
    # After the close a finished session is not stale.
    full = make_series(zigzag(100, 2, 1, 75))
    assert validate_series(full, as_of=datetime(2026, 10, 28, 20, 0, tzinfo=IST)) == []
