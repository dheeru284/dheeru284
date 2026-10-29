"""Technical indicators as pure functions over candle sequences.

Each function returns a list aligned 1:1 with its input, with ``None`` where
the indicator is not yet defined (warm-up) or not computable.
"""

from __future__ import annotations

from collections.abc import Sequence

from .schemas import Candle
from .session import IST


def ema(values: Sequence[float], period: int) -> list[float | None]:
    """Exponential moving average, seeded with the SMA of the first ``period`` values.

    alpha = 2 / (period + 1). The first defined value is at index ``period - 1``.
    """
    if period < 1:
        raise ValueError("period must be >= 1")
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    alpha = 2.0 / (period + 1)
    current = sum(values[:period]) / period
    out[period - 1] = current
    for i in range(period, len(values)):
        current = alpha * values[i] + (1 - alpha) * current
        out[i] = current
    return out


def rsi(closes: Sequence[float], period: int = 14) -> list[float | None]:
    """Wilder's RSI. The first defined value is at index ``period``.

    Averages are seeded with the simple mean of the first ``period`` changes,
    then smoothed as ``avg = (avg * (period - 1) + change) / period``.
    """
    if period < 1:
        raise ValueError("period must be >= 1")
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return out
    changes = [b - a for a, b in zip(closes, closes[1:])]
    avg_gain = sum(max(c, 0.0) for c in changes[:period]) / period
    avg_loss = sum(max(-c, 0.0) for c in changes[:period]) / period
    out[period] = _rsi_value(avg_gain, avg_loss)
    for i in range(period, len(changes)):
        change = changes[i]
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        out[i + 1] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 50.0 if avg_gain == 0 else 100.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def session_vwap(candles: Sequence[Candle]) -> list[float | None]:
    """Volume-weighted average price, anchored to each session's open.

    Uses the typical price (high + low + close) / 3. Resets at the first candle
    of every IST trading day. ``None`` while the session's cumulative volume is
    zero, which is always the case for a spot index such as NIFTY 50.
    """
    out: list[float | None] = []
    session = None
    cum_pv = 0.0
    cum_vol = 0
    for candle in candles:
        day = candle.timestamp.astimezone(IST).date()
        if day != session:
            session, cum_pv, cum_vol = day, 0.0, 0
        typical = (candle.high + candle.low + candle.close) / 3.0
        cum_pv += typical * candle.volume
        cum_vol += candle.volume
        out.append(cum_pv / cum_vol if cum_vol > 0 else None)
    return out


def atr(candles: Sequence[Candle], period: int = 14) -> list[float | None]:
    """Wilder's Average True Range. The first defined value is at index ``period``.

    True range uses the previous close, so the first candle contributes none;
    the seed is the mean of the first ``period`` true ranges.
    """
    if period < 1:
        raise ValueError("period must be >= 1")
    out: list[float | None] = [None] * len(candles)
    if len(candles) <= period:
        return out
    ranges = [
        max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close))
        for p, c in zip(candles, candles[1:])
    ]
    current = sum(ranges[:period]) / period
    out[period] = current
    for i in range(period, len(ranges)):
        current = (current * (period - 1) + ranges[i]) / period
        out[i + 1] = current
    return out
