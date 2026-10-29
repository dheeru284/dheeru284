"""Canonical instrument and candle schemas.

Every market-data provider (the deterministic mock today, Angel One SmartAPI in
Phase 3) must translate its native payloads into these models. Nothing
downstream of a provider (indicators, strategy, API, UI) may depend on a
broker-specific shape.

Conventions:
* Timestamps are timezone-aware and mark the **start** of the candle.
* Prices are in the instrument's quote currency (INR for NSE).
* ``source`` travels with every series so the UI can never present simulated
  data as real.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"  # NSE futures & options
    BFO = "BFO"
    MCX = "MCX"


class InstrumentType(str, Enum):
    INDEX = "INDEX"
    EQUITY = "EQUITY"
    FUTURE = "FUTURE"
    OPTION = "OPTION"


class OptionType(str, Enum):
    CE = "CE"
    PE = "PE"


class Interval(str, Enum):
    """Candle intervals. Names match Angel One SmartAPI's ``interval`` values."""

    ONE_MINUTE = "ONE_MINUTE"
    THREE_MINUTE = "THREE_MINUTE"
    FIVE_MINUTE = "FIVE_MINUTE"
    TEN_MINUTE = "TEN_MINUTE"
    FIFTEEN_MINUTE = "FIFTEEN_MINUTE"
    THIRTY_MINUTE = "THIRTY_MINUTE"
    ONE_HOUR = "ONE_HOUR"

    @property
    def minutes(self) -> int:
        return _INTERVAL_MINUTES[self]

    @property
    def delta(self) -> timedelta:
        return timedelta(minutes=self.minutes)


_INTERVAL_MINUTES = {
    Interval.ONE_MINUTE: 1,
    Interval.THREE_MINUTE: 3,
    Interval.FIVE_MINUTE: 5,
    Interval.TEN_MINUTE: 10,
    Interval.FIFTEEN_MINUTE: 15,
    Interval.THIRTY_MINUTE: 30,
    Interval.ONE_HOUR: 60,
}


class DataSource(str, Enum):
    SIMULATED = "SIMULATED"  # deterministic mock generator, not market data
    BROKER_HISTORICAL = "BROKER_HISTORICAL"  # reserved for Phase 3
    BROKER_LIVE = "BROKER_LIVE"  # reserved for a later phase


class Instrument(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str = Field(min_length=1, description="Canonical symbol, e.g. NIFTY")
    display_name: str
    exchange: Exchange
    instrument_type: InstrumentType
    tick_size: float = Field(gt=0)
    lot_size: int = Field(ge=1)
    expiry: date | None = None
    strike: float | None = Field(default=None, gt=0)
    option_type: OptionType | None = None
    broker_token: str | None = Field(
        default=None, description="Provider-specific token, resolved from the scrip master"
    )

    @model_validator(mode="after")
    def _derivative_fields(self) -> Instrument:
        is_option = self.instrument_type is InstrumentType.OPTION
        is_derivative = self.instrument_type in (InstrumentType.FUTURE, InstrumentType.OPTION)
        if is_derivative and self.expiry is None:
            raise ValueError("futures and options require an expiry")
        if not is_derivative and self.expiry is not None:
            raise ValueError("only futures and options carry an expiry")
        if is_option != (self.strike is not None and self.option_type is not None):
            raise ValueError("options require strike and option_type; other types must omit both")
        return self


class Candle(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: datetime = Field(description="Candle start, timezone-aware")
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: int = Field(ge=0)

    @field_validator("timestamp")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value

    @field_validator("open", "high", "low", "close")
    @classmethod
    def _finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("price must be finite")
        return value

    @model_validator(mode="after")
    def _ohlc(self) -> Candle:
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("high/low must bound open and close")
        return self


class CandleSeries(BaseModel):
    """An ordered run of candles for one instrument and interval.

    Structural problems (gaps, ordering, alignment) are deliberately *not*
    rejected here: providers must be able to hand over what they received so
    :func:`optionpulse.validation.validate_series` can report it and the
    strategy can return ``DATA_INVALID`` instead of crashing.
    """

    instrument: Instrument
    interval: Interval
    source: DataSource
    candles: list[Candle]
