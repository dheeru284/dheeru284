"""The strategy library: every rule set the portal runs, described and executable.

Each strategy answers two questions about a *closed* candle ``i``:

* ``setup(m, i)``: does it want to go LONG, SHORT or nothing, and which
  checks passed or failed?
* ``exits(side, entry, m, i)``: where would the stop and target sit for an
  entry at ``entry`` (the next candle's open)?

Entering, managing and exiting the paper trade is the engine's job
(``engine.py``), so every strategy is traded under identical rules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from enum import Enum

from pydantic import BaseModel

from .indicators import atr, ema, rsi, session_vwap
from .schemas import Candle, CandleSeries
from .session import IST
from .strategy import Check, StrategyConfig, trend_checks


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class Market:
    """A candle series with every indicator the strategies need, precomputed once."""

    candles: list[Candle]
    ema_fast: list[float | None]
    ema_slow: list[float | None]
    vwap: list[float | None]
    rsi: list[float | None]
    atr: list[float | None]
    day: list[date]
    bar_of_day: list[int]  # 0 = the 09:15 candle
    day_start: list[int]  # index of the first candle of this candle's day

    @classmethod
    def build(cls, series: CandleSeries, config: StrategyConfig = StrategyConfig()) -> Market:
        candles = series.candles
        closes = [c.close for c in candles]
        days = [c.timestamp.astimezone(IST).date() for c in candles]
        bar_of_day, day_start = [], []
        start = 0
        for i, d in enumerate(days):
            if i == 0 or d != days[i - 1]:
                start = i
            day_start.append(start)
            first = candles[start].timestamp.astimezone(IST)
            open_ = first.replace(hour=9, minute=15, second=0, microsecond=0)
            bar_of_day.append(int((candles[i].timestamp - open_).total_seconds() // (series.interval.minutes * 60)))
        return cls(
            candles=candles,
            ema_fast=ema(closes, config.ema_fast),
            ema_slow=ema(closes, config.ema_slow),
            vwap=session_vwap(candles),
            rsi=rsi(closes, config.rsi_period),
            atr=atr(candles, 14),
            day=days,
            bar_of_day=bar_of_day,
            day_start=day_start,
        )


class Setup(BaseModel):
    side: Side | None
    long_checks: list[Check]
    short_checks: list[Check]
    note: str = ""


class StrategyInfo(BaseModel):
    id: str
    name: str
    style: str
    summary: str
    how_it_works: list[str]
    long_rules: list[str]
    short_rules: list[str]
    exit_rules: list[str]
    parameters: dict[str, str]
    works_best: str
    struggles: str
    one_trade_per_side_per_day: bool = False


def _not_ready(reason: str) -> Setup:
    return Setup(side=None, long_checks=[], short_checks=[], note=reason)


def _pick(long_checks: list[Check], short_checks: list[Check]) -> Side | None:
    if long_checks and all(c.passed for c in long_checks):
        return Side.LONG
    if short_checks and all(c.passed for c in short_checks):
        return Side.SHORT
    return None


class Strategy(ABC):
    info: StrategyInfo

    @abstractmethod
    def setup(self, m: Market, i: int) -> Setup: ...

    @abstractmethod
    def exits(self, side: Side, entry: float, m: Market, i: int) -> tuple[float, float]:
        """(stop, target) for an entry at ``entry`` triggered by candle ``i``."""


class TrendPulse(Strategy):
    def __init__(self, config: StrategyConfig = StrategyConfig(), stop_atr: float = 1.0, target_atr: float = 2.0):
        self.config, self.stop_atr, self.target_atr = config, stop_atr, target_atr
        c = config
        self.info = StrategyInfo(
            id="trend_pulse",
            name="Trend Pulse",
            style="Trend following",
            summary="Rides an intraday trend once short-term averages, VWAP and momentum all agree.",
            how_it_works=[
                f"EMA {c.ema_fast} vs EMA {c.ema_slow} gives the short-term trend direction.",
                "Session VWAP shows whether buyers or sellers have paid up on average today.",
                f"RSI {c.rsi_period} must show momentum without being stretched, so it avoids chasing.",
            ],
            long_rules=[f"EMA {c.ema_fast} above EMA {c.ema_slow}", "Close above VWAP",
                        f"Close above EMA {c.ema_fast}", f"RSI between {c.long_rsi_min:g} and {c.long_rsi_max:g}"],
            short_rules=[f"EMA {c.ema_fast} below EMA {c.ema_slow}", "Close below VWAP",
                         f"Close below EMA {c.ema_fast}", f"RSI between {c.short_rsi_min:g} and {c.short_rsi_max:g}"],
            exit_rules=[f"Stop {stop_atr:g} × ATR(14) from entry", f"Target {target_atr:g} × ATR(14) from entry (2R)",
                        "Square off at 15:20 if neither is hit"],
            parameters={"EMA fast": str(c.ema_fast), "EMA slow": str(c.ema_slow), "RSI": str(c.rsi_period),
                        "Stop": f"{stop_atr:g} ATR", "Target": f"{target_atr:g} ATR"},
            works_best="Steady one-directional days.",
            struggles="Choppy, range-bound sessions where the averages keep crossing.",
        )

    def setup(self, m: Market, i: int) -> Setup:
        fast, slow, vwap, strength = m.ema_fast[i], m.ema_slow[i], m.vwap[i], m.rsi[i]
        if None in (fast, slow, vwap, strength):
            return _not_ready("indicators warming up" if vwap is not None else "no volume for VWAP")
        long_c, short_c = trend_checks(m.candles[i].close, fast, slow, vwap, strength, self.config)
        return Setup(side=_pick(long_c, short_c), long_checks=long_c, short_checks=short_c)

    def exits(self, side: Side, entry: float, m: Market, i: int) -> tuple[float, float]:
        a = m.atr[i] or 0.0
        sign = 1 if side is Side.LONG else -1
        return entry - sign * self.stop_atr * a, entry + sign * self.target_atr * a


class OpeningRangeBreakout(Strategy):
    def __init__(self, range_bars: int = 3, last_signal_bar: int = 45, max_stop_atr: float = 1.5):
        self.range_bars, self.last_signal_bar, self.max_stop_atr = range_bars, last_signal_bar, max_stop_atr
        minutes = range_bars * 5
        self.info = StrategyInfo(
            id="orb",
            name="Opening Range Breakout",
            style="Breakout",
            summary=f"Trades the first decisive break of the first {minutes} minutes' high or low.",
            how_it_works=[
                f"The opening range is the high and low of 09:15–09:{15 + minutes:02d}, when overnight news gets priced.",
                "A close beyond that range shows one side has won the opening auction.",
                "VWAP confirms that the break has volume behind it.",
            ],
            long_rules=["Candle closes above the opening-range high", "Previous close was at or below it (fresh break)",
                        "Close above VWAP", "Signal before 13:00"],
            short_rules=["Candle closes below the opening-range low", "Previous close was at or above it (fresh break)",
                         "Close below VWAP", "Signal before 13:00"],
            exit_rules=[f"Stop at the opposite side of the range, but no more than {max_stop_atr:g} × ATR away",
                        "Target 2 × the risk (2R)", "One trade per direction per day", "Square off at 15:20"],
            parameters={"Range": f"{minutes} min", "Last signal": "13:00", "Max stop": f"{max_stop_atr:g} ATR",
                        "Target": "2R"},
            works_best="Days with a clear overnight catalyst (global cues, oil, results).",
            struggles="Quiet days where the range breaks and immediately reverses.",
            one_trade_per_side_per_day=True,
        )

    def _range(self, m: Market, i: int) -> tuple[float, float]:
        start = m.day_start[i]
        bars = m.candles[start : start + self.range_bars]
        return max(c.high for c in bars), min(c.low for c in bars)

    def setup(self, m: Market, i: int) -> Setup:
        if m.bar_of_day[i] < self.range_bars or i - m.day_start[i] < self.range_bars:
            return _not_ready("opening range still forming")
        if m.bar_of_day[m.day_start[i]] != 0:
            return _not_ready("opening candles missing from the data")
        if m.bar_of_day[i] > self.last_signal_bar:
            return _not_ready("past 13:00, no new breakouts")
        vwap = m.vwap[i]
        if vwap is None:
            return _not_ready("no volume for VWAP")
        hi, lo = self._range(m, i)
        close, prev = m.candles[i].close, m.candles[i - 1].close
        long_c = [
            Check(name="breakout", passed=close > hi, detail=f"close {close:.2f} vs range high {hi:.2f}"),
            Check(name="fresh", passed=prev <= hi, detail=f"previous close {prev:.2f}"),
            Check(name="vwap", passed=close > vwap, detail=f"close vs VWAP {vwap:.2f}"),
        ]
        short_c = [
            Check(name="breakdown", passed=close < lo, detail=f"close {close:.2f} vs range low {lo:.2f}"),
            Check(name="fresh", passed=prev >= lo, detail=f"previous close {prev:.2f}"),
            Check(name="vwap", passed=close < vwap, detail=f"close vs VWAP {vwap:.2f}"),
        ]
        return Setup(side=_pick(long_c, short_c), long_checks=long_c, short_checks=short_c,
                     note=f"range {lo:.2f} – {hi:.2f}")

    def exits(self, side: Side, entry: float, m: Market, i: int) -> tuple[float, float]:
        hi, lo = self._range(m, i)
        a = m.atr[i]
        cap = self.max_stop_atr * a if a else float("inf")  # no ATR yet: use the range alone
        if side is Side.LONG:
            stop = max(lo, entry - cap)
            return stop, entry + 2 * (entry - stop)
        stop = min(hi, entry + cap)
        return stop, entry - 2 * (stop - entry)


class VwapSnapBack(Strategy):
    def __init__(self, stretch_atr: float = 1.5, stop_atr: float = 1.0, first_bar: int = 6, last_bar: int = 63):
        self.stretch_atr, self.stop_atr, self.first_bar, self.last_bar = stretch_atr, stop_atr, first_bar, last_bar
        self.info = StrategyInfo(
            id="vwap_snapback",
            name="VWAP Snap-back",
            style="Mean reversion",
            summary="Fades sharp overextensions away from VWAP once a reversal candle appears.",
            how_it_works=[
                "Intraday prices tend to get pulled back toward the day's VWAP after a sharp, emotional move.",
                f"It waits until price is more than {stretch_atr:g} × ATR from VWAP and RSI is at an extreme.",
                "A candle closing against the move is the first sign the stretch is ending.",
            ],
            long_rules=[f"Close at least {stretch_atr:g} × ATR below VWAP", "RSI 30 or lower",
                        "Green candle (close above open)", "Between 09:45 and 14:30"],
            short_rules=[f"Close at least {stretch_atr:g} × ATR above VWAP", "RSI 70 or higher",
                         "Red candle (close below open)", "Between 09:45 and 14:30"],
            exit_rules=["Target: back to VWAP (as it stood at the signal)", f"Stop {stop_atr:g} × ATR from entry",
                        "Skip if price has already reached VWAP at entry", "Square off at 15:20"],
            parameters={"Stretch": f"{stretch_atr:g} ATR", "RSI": "≤30 / ≥70", "Stop": f"{stop_atr:g} ATR",
                        "Target": "VWAP"},
            works_best="Range-bound days with spikes on headlines.",
            struggles="Strong trend days, where stretched keeps getting more stretched.",
        )

    def setup(self, m: Market, i: int) -> Setup:
        if not (self.first_bar <= m.bar_of_day[i] <= self.last_bar):
            return _not_ready("outside 09:45–14:30")
        vwap, strength, a = m.vwap[i], m.rsi[i], m.atr[i]
        if None in (vwap, strength, a):
            return _not_ready("indicators warming up" if vwap is not None else "no volume for VWAP")
        c = m.candles[i]
        gap = (c.close - vwap) / a if a else 0.0
        long_c = [
            Check(name="stretch", passed=gap <= -self.stretch_atr, detail=f"{gap:+.2f} ATR from VWAP {vwap:.2f}"),
            Check(name="rsi", passed=strength <= 30, detail=f"RSI {strength:.1f} ≤ 30"),
            Check(name="reversal", passed=c.close > c.open, detail=f"candle {c.open:.2f} → {c.close:.2f}"),
        ]
        short_c = [
            Check(name="stretch", passed=gap >= self.stretch_atr, detail=f"{gap:+.2f} ATR from VWAP {vwap:.2f}"),
            Check(name="rsi", passed=strength >= 70, detail=f"RSI {strength:.1f} ≥ 70"),
            Check(name="reversal", passed=c.close < c.open, detail=f"candle {c.open:.2f} → {c.close:.2f}"),
        ]
        return Setup(side=_pick(long_c, short_c), long_checks=long_c, short_checks=short_c)

    def exits(self, side: Side, entry: float, m: Market, i: int) -> tuple[float, float]:
        a, vwap = m.atr[i] or 0.0, m.vwap[i] or entry
        if side is Side.LONG:
            return entry - self.stop_atr * a, vwap
        return entry + self.stop_atr * a, vwap


def default_strategies() -> list[Strategy]:
    return [TrendPulse(), OpeningRangeBreakout(), VwapSnapBack()]
