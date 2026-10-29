from datetime import date, datetime

import pytest
from pydantic import ValidationError

from optionpulse.schemas import Candle, Exchange, Instrument, InstrumentType, Interval, OptionType
from optionpulse.session import IST

TS = datetime(2026, 10, 28, 9, 15, tzinfo=IST)


def candle(**kw):
    base = dict(timestamp=TS, open=100.0, high=101.0, low=99.0, close=100.5, volume=10)
    return Candle(**(base | kw))


def test_valid_candle():
    assert candle().close == 100.5


@pytest.mark.parametrize(
    "kw",
    [
        {"timestamp": datetime(2026, 10, 28, 9, 15)},  # naive
        {"high": 100.2},  # below close
        {"low": 100.4},  # above open
        {"open": 0.0},
        {"close": -1.0},
        {"high": float("inf")},
        {"volume": -1},
    ],
)
def test_invalid_candles_rejected(kw):
    with pytest.raises(ValidationError):
        candle(**kw)


def test_candle_is_immutable():
    with pytest.raises(ValidationError):
        candle().close = 1.0


def test_interval_minutes():
    assert Interval.FIVE_MINUTE.minutes == 5
    assert Interval.ONE_HOUR.delta.total_seconds() == 3600


def _instrument(**kw):
    base = dict(symbol="NIFTY", display_name="NIFTY 50", exchange=Exchange.NSE,
                instrument_type=InstrumentType.INDEX, tick_size=0.05, lot_size=1)
    return Instrument(**(base | kw))


def test_index_instrument():
    assert _instrument().expiry is None


def test_option_requires_strike_type_and_expiry():
    opt = _instrument(exchange=Exchange.NFO, instrument_type=InstrumentType.OPTION, lot_size=75,
                      expiry=date(2026, 11, 3), strike=25000.0, option_type=OptionType.CE)
    assert opt.option_type is OptionType.CE
    with pytest.raises(ValidationError):
        _instrument(instrument_type=InstrumentType.OPTION, expiry=date(2026, 11, 3), strike=25000.0)
    with pytest.raises(ValidationError):
        _instrument(instrument_type=InstrumentType.OPTION, strike=25000.0, option_type=OptionType.PE)


def test_future_requires_expiry_and_index_rejects_one():
    with pytest.raises(ValidationError):
        _instrument(instrument_type=InstrumentType.FUTURE)
    with pytest.raises(ValidationError):
        _instrument(expiry=date(2026, 11, 3))
    with pytest.raises(ValidationError):
        _instrument(strike=25000.0, option_type=OptionType.CE)
