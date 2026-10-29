"""Rule-based intraday setup detector (EMA 9/21 trend, session VWAP, RSI 14).

The strategy only *describes* the last closed candle. It does not size, route
or place orders, and a setup is not a recommendation to trade.

Rules, evaluated on the latest completed candle:

LONG_SETUP when all hold
  1. EMA fast > EMA slow                  (short-term trend up)
  2. close > session VWAP                 (buyers in control today)
  3. close > EMA fast                     (price riding the fast average)
  4. long_rsi_min <= RSI <= long_rsi_max  (momentum, not yet overbought)

SHORT_SETUP is the mirror image (EMA fast < slow, close < VWAP, close < EMA
fast, short_rsi_min <= RSI <= short_rsi_max).

NO_TRADE when the data is sound but neither side passes every check.

DATA_INVALID when the series fails validation, is too short for the
indicators to warm up, or VWAP cannot be computed (no volume).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .indicators import ema, rsi, session_vwap
from .schemas import CandleSeries, DataSource, Interval
from .validation import DataIssue, validate_series


class Signal(str, Enum):
    LONG_SETUP = "LONG_SETUP"
    SHORT_SETUP = "SHORT_SETUP"
    NO_TRADE = "NO_TRADE"
    DATA_INVALID = "DATA_INVALID"


class StrategyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    ema_fast: int = Field(default=9, ge=1)
    ema_slow: int = Field(default=21, ge=2)
    rsi_period: int = Field(default=14, ge=1)
    min_bars: int = Field(default=30, ge=1)
    long_rsi_min: float = 55.0
    long_rsi_max: float = 70.0
    short_rsi_min: float = 30.0
    short_rsi_max: float = 45.0
    max_staleness_bars: int = Field(default=2, ge=1)

    @model_validator(mode="after")
    def _consistent(self) -> StrategyConfig:
        if self.ema_fast >= self.ema_slow:
            raise ValueError("ema_fast must be shorter than ema_slow")
        if self.min_bars < max(self.ema_slow, self.rsi_period + 1):
            raise ValueError("min_bars must cover the indicator warm-up")
        if not (0 <= self.short_rsi_min <= self.short_rsi_max <= 100):
            raise ValueError("invalid short RSI band")
        if not (0 <= self.long_rsi_min <= self.long_rsi_max <= 100):
            raise ValueError("invalid long RSI band")
        return self


class Check(BaseModel):
    name: str
    passed: bool
    detail: str


class IndicatorSnapshot(BaseModel):
    close: float
    ema_fast: float
    ema_slow: float
    vwap: float
    rsi: float


class StrategyResult(BaseModel):
    signal: Signal
    symbol: str
    interval: Interval
    source: DataSource
    evaluated_candle: datetime | None = Field(description="Start of the candle the signal describes")
    reasons: list[str]
    long_checks: list[Check] = []
    short_checks: list[Check] = []
    indicators: IndicatorSnapshot | None = None
    issues: list[DataIssue] = []


@dataclass(frozen=True)
class IndicatorSeries:
    ema_fast: list[float | None]
    ema_slow: list[float | None]
    vwap: list[float | None]
    rsi: list[float | None]


def compute_indicators(series: CandleSeries, config: StrategyConfig) -> IndicatorSeries:
    closes = [c.close for c in series.candles]
    return IndicatorSeries(
        ema_fast=ema(closes, config.ema_fast),
        ema_slow=ema(closes, config.ema_slow),
        vwap=session_vwap(series.candles),
        rsi=rsi(closes, config.rsi_period),
    )


def evaluate(
    series: CandleSeries,
    config: StrategyConfig | None = None,
    as_of: datetime | None = None,
) -> StrategyResult:
    config = config or StrategyConfig()
    base = dict(symbol=series.instrument.symbol, interval=series.interval, source=series.source)
    last = series.candles[-1].timestamp if series.candles else None

    issues = validate_series(series, as_of=as_of, max_staleness_bars=config.max_staleness_bars)
    if issues:
        return StrategyResult(
            signal=Signal.DATA_INVALID,
            evaluated_candle=last,
            reasons=[f"{i.code.value}: {i.message}" for i in issues[:5]],
            issues=issues,
            **base,
        )
    if len(series.candles) < config.min_bars:
        return StrategyResult(
            signal=Signal.DATA_INVALID,
            evaluated_candle=last,
            reasons=[f"INSUFFICIENT_HISTORY: {len(series.candles)} candles, need {config.min_bars}"],
            **base,
        )

    ind = compute_indicators(series, config)
    close = series.candles[-1].close
    fast, slow, vwap, strength = ind.ema_fast[-1], ind.ema_slow[-1], ind.vwap[-1], ind.rsi[-1]
    if vwap is None:
        return StrategyResult(
            signal=Signal.DATA_INVALID,
            evaluated_candle=last,
            reasons=["VWAP_UNAVAILABLE: session has zero volume (spot indices carry none)"],
            **base,
        )
    # min_bars covers the warm-up, so these are defined; keep the type checker honest.
    assert fast is not None and slow is not None and strength is not None

    snapshot = IndicatorSnapshot(close=close, ema_fast=fast, ema_slow=slow, vwap=vwap, rsi=strength)
    f, s = f"EMA{config.ema_fast}", f"EMA{config.ema_slow}"
    long_checks = [
        Check(name="trend", passed=fast > slow, detail=f"{f} {fast:.2f} vs {s} {slow:.2f}"),
        Check(name="vwap", passed=close > vwap, detail=f"close {close:.2f} vs VWAP {vwap:.2f}"),
        Check(name="ema_fast", passed=close > fast, detail=f"close {close:.2f} vs {f} {fast:.2f}"),
        Check(
            name="rsi",
            passed=config.long_rsi_min <= strength <= config.long_rsi_max,
            detail=f"RSI {strength:.1f} in [{config.long_rsi_min:g}, {config.long_rsi_max:g}]",
        ),
    ]
    short_checks = [
        Check(name="trend", passed=fast < slow, detail=f"{f} {fast:.2f} vs {s} {slow:.2f}"),
        Check(name="vwap", passed=close < vwap, detail=f"close {close:.2f} vs VWAP {vwap:.2f}"),
        Check(name="ema_fast", passed=close < fast, detail=f"close {close:.2f} vs {f} {fast:.2f}"),
        Check(
            name="rsi",
            passed=config.short_rsi_min <= strength <= config.short_rsi_max,
            detail=f"RSI {strength:.1f} in [{config.short_rsi_min:g}, {config.short_rsi_max:g}]",
        ),
    ]

    if all(c.passed for c in long_checks):
        signal, reasons = Signal.LONG_SETUP, ["all long conditions met"]
    elif all(c.passed for c in short_checks):
        signal, reasons = Signal.SHORT_SETUP, ["all short conditions met"]
    else:
        signal = Signal.NO_TRADE
        reasons = [
            f"long failed: {', '.join(c.name for c in long_checks if not c.passed)}",
            f"short failed: {', '.join(c.name for c in short_checks if not c.passed)}",
        ]
    return StrategyResult(
        signal=signal,
        evaluated_candle=last,
        reasons=reasons,
        long_checks=long_checks,
        short_checks=short_checks,
        indicators=snapshot,
        **base,
    )
