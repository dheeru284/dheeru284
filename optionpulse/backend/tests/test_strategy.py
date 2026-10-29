from datetime import timedelta

import pytest
from pydantic import ValidationError

from optionpulse.schemas import Candle, Interval
from optionpulse.strategy import Signal, StrategyConfig, evaluate

from .conftest import make_series, zigzag


def test_long_setup():
    # +3 / -1.5 zigzag: steady uptrend, RSI settles near 66.7, last move is up.
    result = evaluate(make_series(zigzag(25000, 3, 1.5, 40)))
    assert result.signal is Signal.LONG_SETUP
    assert all(c.passed for c in result.long_checks)
    snap = result.indicators
    assert snap.ema_fast > snap.ema_slow and snap.close > snap.vwap
    assert 55 <= snap.rsi <= 70


def test_short_setup():
    # Mirror image: -3 / +1.5, RSI near 33.3, last move is down.
    result = evaluate(make_series(zigzag(25000, -3, -1.5, 40)))
    assert result.signal is Signal.SHORT_SETUP
    assert all(c.passed for c in result.short_checks)
    assert 30 <= result.indicators.rsi <= 45


def test_overbought_trend_is_no_trade():
    result = evaluate(make_series([25000 + 5 * i for i in range(40)]))
    assert result.signal is Signal.NO_TRADE
    failed = {c.name for c in result.long_checks if not c.passed}
    assert failed == {"rsi"}  # RSI 100 is above the long band
    assert result.indicators is not None


def test_choppy_market_is_no_trade():
    closes = [25000 + (2 if i % 2 else -2) for i in range(40)]
    assert evaluate(make_series(closes)).signal is Signal.NO_TRADE


def test_result_carries_source_and_last_candle():
    series = make_series(zigzag(25000, 3, 1.5, 40))
    result = evaluate(series)
    assert result.source.value == "SIMULATED"
    assert result.evaluated_candle == series.candles[-1].timestamp
    assert result.symbol == "NIFTY" and result.interval is Interval.FIVE_MINUTE


@pytest.mark.parametrize("n", [0, 1, 29])
def test_insufficient_history_is_data_invalid(n):
    series = make_series(zigzag(25000, 3, 1.5, max(n, 1)))
    if n == 0:
        series = series.model_copy(update={"candles": []})
    result = evaluate(series)
    assert result.signal is Signal.DATA_INVALID
    assert result.indicators is None


def test_exactly_min_bars_is_evaluated():
    assert evaluate(make_series(zigzag(25000, 3, 1.5, 30))).signal is not Signal.DATA_INVALID


def test_gap_is_data_invalid():
    s = make_series(zigzag(25000, 3, 1.5, 40))
    s = s.model_copy(update={"candles": s.candles[:20] + s.candles[21:]})
    result = evaluate(s)
    assert result.signal is Signal.DATA_INVALID
    assert result.issues[0].code.value == "GAP"


def test_zero_volume_is_data_invalid():
    result = evaluate(make_series(zigzag(25000, 3, 1.5, 40), volumes=[0] * 40))
    assert result.signal is Signal.DATA_INVALID
    assert "VWAP_UNAVAILABLE" in result.reasons[0]


def test_corrupt_candle_is_data_invalid():
    s = make_series(zigzag(25000, 3, 1.5, 40))
    last = s.candles[-1]
    bad = Candle.model_construct(timestamp=last.timestamp, open=last.open, high=last.low - 5,
                                 low=last.low, close=last.close, volume=last.volume)
    result = evaluate(s.model_copy(update={"candles": s.candles[:-1] + [bad]}))
    assert result.signal is Signal.DATA_INVALID


def test_stale_data_is_data_invalid():
    s = make_series(zigzag(25000, 3, 1.5, 40))
    last_end = s.candles[-1].timestamp + Interval.FIVE_MINUTE.delta
    assert evaluate(s, as_of=last_end).signal is Signal.LONG_SETUP
    assert evaluate(s, as_of=last_end + timedelta(minutes=30)).signal is Signal.DATA_INVALID


def test_custom_rsi_band_changes_outcome():
    s = make_series(zigzag(25000, 3, 1.5, 40))
    narrow = StrategyConfig(long_rsi_min=60, long_rsi_max=65)
    assert evaluate(s, narrow).signal is Signal.NO_TRADE


def test_deterministic():
    s = make_series(zigzag(25000, 3, 1.5, 40))
    assert evaluate(s) == evaluate(s)


@pytest.mark.parametrize(
    "kw",
    [
        {"ema_fast": 21, "ema_slow": 9},
        {"min_bars": 10},
        {"long_rsi_min": 80, "long_rsi_max": 70},
        {"short_rsi_max": 120},
    ],
)
def test_config_validation(kw):
    with pytest.raises(ValidationError):
        StrategyConfig(**kw)
