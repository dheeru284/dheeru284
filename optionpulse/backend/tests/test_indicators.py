from datetime import date

import pytest

from optionpulse.indicators import ema, rsi, session_vwap
from optionpulse.schemas import Interval

from .conftest import make_series

# StockCharts' published Wilder RSI(14) worked example. Their spreadsheet rounds
# the seed averages to 0.24 / 0.10, which lifts every value by ~0.07; computed
# exactly the first RSI is 100 - 100 / (1 + (3.34/14) / (1.40/14)) = 70.464.
STOCKCHARTS_CLOSES = [
    44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
    45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64,
]
STOCKCHARTS_RSI = [70.53, 66.32, 66.55, 69.41, 66.36, 57.97]


def test_ema_seeded_with_sma_then_smoothed():
    values = [1, 2, 3, 4, 5, 6]
    out = ema(values, 3)
    assert out[:2] == [None, None]
    assert out[2] == pytest.approx(2.0)  # SMA(1,2,3)
    assert out[3] == pytest.approx(0.5 * 4 + 0.5 * 2.0)  # alpha = 2/(3+1)
    assert out[4] == pytest.approx(0.5 * 5 + 0.5 * 3.0)
    assert out[5] == pytest.approx(5.0)


def test_ema_constant_and_short_input():
    assert ema([7.0] * 30, 9)[-1] == pytest.approx(7.0)
    assert ema([1.0, 2.0], 9) == [None, None]
    with pytest.raises(ValueError):
        ema([1.0], 0)


def test_ema_period_one_is_identity():
    assert ema([3.0, 1.0, 4.0], 1) == [3.0, 1.0, 4.0]


def test_rsi_matches_stockcharts_reference():
    out = rsi(STOCKCHARTS_CLOSES, 14)
    assert out[:14] == [None] * 14
    assert out[14] == pytest.approx(100 - 100 / (1 + 3.34 / 1.40))
    assert [round(v, 2) for v in out[14:]] == [70.46, 66.25, 66.48, 69.35, 66.29, 57.92]
    assert all(abs(a - b) < 0.1 for a, b in zip(out[14:], STOCKCHARTS_RSI))


def test_rsi_extremes():
    assert rsi([float(i) for i in range(20)], 14)[-1] == 100.0
    assert rsi([float(20 - i) for i in range(20)], 14)[-1] == pytest.approx(0.0)
    assert rsi([5.0] * 20, 14)[-1] == 50.0
    assert rsi([1.0] * 14, 14) == [None] * 14


def test_rsi_stays_in_bounds():
    closes = [100 + ((i * 37) % 11) - 5 for i in range(200)]
    assert all(0 <= v <= 100 for v in rsi(closes, 14) if v is not None)


def test_vwap_cumulative_typical_price():
    series = make_series([100.0, 102.0, 101.0], volumes=[100, 300, 0])
    c = series.candles
    tp = [(x.high + x.low + x.close) / 3 for x in c]
    out = session_vwap(c)
    assert out[0] == pytest.approx(tp[0])
    assert out[1] == pytest.approx((tp[0] * 100 + tp[1] * 300) / 400)
    assert out[2] == out[1]  # zero-volume bar leaves VWAP unchanged


def test_vwap_resets_each_session():
    day1 = make_series([100.0, 110.0], day=date(2026, 10, 27))
    day2 = make_series([200.0, 201.0], day=date(2026, 10, 28))
    out = session_vwap(day1.candles + day2.candles)
    tp = (day2.candles[0].high + day2.candles[0].low + day2.candles[0].close) / 3
    assert out[2] == pytest.approx(tp)


def test_vwap_undefined_without_volume():
    series = make_series([100.0, 101.0], volumes=[0, 0], interval=Interval.FIVE_MINUTE)
    assert session_vwap(series.candles) == [None, None]
