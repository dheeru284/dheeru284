"""Deterministic simulated market data.

Output depends only on ``(seed, symbol, trading day)``. The generator uses
its own SplitMix64 PRNG and SHA-256 seeding rather than ``random`` or the
per-process salted ``hash()``, so results do not drift between Python
versions or runs; a golden fingerprint test pins the output. Each day is generated independently at one-minute
resolution and aggregated, so different windows and intervals always agree.

Everything produced here is labelled ``DataSource.SIMULATED``. It is not
market data and the volume in particular is invented: the real NIFTY 50 spot
index has no traded volume.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache

from ..macro import MacroPoint, MacroSource
from ..schemas import Candle, CandleSeries, DataSource, Exchange, Instrument, InstrumentType, Interval
from ..session import IST, bar_starts, is_trading_day
from .base import MarketDataProvider, UnknownInstrument, UnsupportedInterval

MINUTES_PER_SESSION = 375
SUPPORTED_INTERVALS = tuple(
    i for i in Interval if MINUTES_PER_SESSION % i.minutes == 0
)  # 1, 3, 5 and 15 minutes divide the 09:15-15:30 session exactly


@dataclass(frozen=True)
class _Profile:
    anchor: float  # long-run price level
    minute_vol: float  # stdev of one-minute log return
    base_volume: int  # shares/contracts per minute at mid-session
    tick: float = 0.05
    gap_sd: float = 0.006  # stdev of the overnight gap (log return)


_INSTRUMENTS = {
    "NIFTY": Instrument(
        symbol="NIFTY",
        display_name="NIFTY 50",
        exchange=Exchange.NSE,
        instrument_type=InstrumentType.INDEX,
        tick_size=0.05,
        lot_size=1,
    ),
    "BANKNIFTY": Instrument(
        symbol="BANKNIFTY",
        display_name="NIFTY BANK",
        exchange=Exchange.NSE,
        instrument_type=InstrumentType.INDEX,
        tick_size=0.05,
        lot_size=1,
    ),
}
_PROFILES = {
    "NIFTY": _Profile(anchor=24_500.0, minute_vol=0.00042, base_volume=9_000),
    "BANKNIFTY": _Profile(anchor=52_000.0, minute_vol=0.00055, base_volume=4_000),
}
# Simulated cross-market factors, sampled on the NSE session grid only.
_MACRO_PROFILES = {
    "BRENT": _Profile(anchor=66.0, minute_vol=0.00055, base_volume=0, tick=0.01, gap_sd=0.012),
    "WTI": _Profile(anchor=62.0, minute_vol=0.00055, base_volume=0, tick=0.01, gap_sd=0.012),
    "USDINR": _Profile(anchor=88.0, minute_vol=0.00007, base_volume=0, tick=0.0025, gap_sd=0.0015),
    "INDIAVIX": _Profile(anchor=13.0, minute_vol=0.0016, base_volume=0, tick=0.0025, gap_sd=0.04),
    "GOLD": _Profile(anchor=4_000.0, minute_vol=0.0003, base_volume=0, tick=0.1, gap_sd=0.006),
    "SPX_FUT": _Profile(anchor=6_800.0, minute_vol=0.0003, base_volume=0, tick=0.25),
    "US10Y": _Profile(anchor=4.2, minute_vol=0.0005, base_volume=0, tick=0.001, gap_sd=0.008),
}


class _SplitMix64:
    _MASK = (1 << 64) - 1

    def __init__(self, seed: int) -> None:
        self._state = seed & self._MASK

    def next_u64(self) -> int:
        self._state = (self._state + 0x9E3779B97F4A7C15) & self._MASK
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & self._MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & self._MASK
        return z ^ (z >> 31)

    def uniform(self) -> float:
        """Uniform on the open interval (0, 1)."""
        return ((self.next_u64() >> 11) + 0.5) / float(1 << 53)

    def gauss(self) -> float:
        """Standard normal via Box-Muller (one value per call, the pair's cosine half)."""
        u1, u2 = self.uniform(), self.uniform()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def _seed_for(seed: int, symbol: str, day: date) -> int:
    digest = hashlib.sha256(f"optionpulse|{seed}|{symbol}|{day.isoformat()}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _round_tick(price: float, tick: float) -> float:
    return round(round(price / tick) * tick, 4)


@lru_cache(maxsize=256)
def _minute_bars(seed: int, symbol: str, day: date) -> tuple[Candle, ...]:
    profile = _PROFILES.get(symbol) or _MACRO_PROFILES[symbol]
    tick = profile.tick
    rng = _SplitMix64(_seed_for(seed, symbol, day))

    # Day open: a slow ~90-day cycle around the anchor plus an overnight gap.
    cycle = 0.05 * math.sin(2 * math.pi * day.toordinal() / 90.0)
    price = profile.anchor * math.exp(cycle * profile.gap_sd / 0.006 + profile.gap_sd * rng.gauss())

    # Regime for the day: trend up, trend down or mean-reverting range, so
    # the strategy sees all of its outcomes across a week of sessions.
    roll = rng.uniform()
    if roll < 0.35:
        drift = 0.010 / MINUTES_PER_SESSION
    elif roll < 0.70:
        drift = -0.010 / MINUTES_PER_SESSION
    else:
        drift = 0.0
    reversion = 0.01 if drift == 0.0 else 0.0  # per-minute pull toward the open
    day_open = price

    bars = []
    for minute, start in enumerate(bar_starts(day, Interval.ONE_MINUTE)):
        pull = -reversion * math.log(price / day_open)
        ret = drift + pull + profile.minute_vol * rng.gauss()
        open_ = price
        close = open_ * math.exp(ret)
        wick = profile.minute_vol * 0.6
        high = max(open_, close) * (1 + abs(rng.gauss()) * wick)
        low = min(open_, close) * (1 - abs(rng.gauss()) * wick)
        # U-shaped intraday volume: heavy at the open and into the close.
        shape = 1 + 1.6 * math.exp(-minute / 25.0) + 1.1 * math.exp(-(MINUTES_PER_SESSION - 1 - minute) / 25.0)
        volume = int(profile.base_volume * shape * math.exp(0.35 * rng.gauss()))
        bars.append(
            Candle(
                timestamp=start,
                open=_round_tick(open_, tick),
                high=_round_tick(high, tick),
                low=_round_tick(low, tick),
                close=_round_tick(close, tick),
                volume=volume,
            )
        )
        price = close
    return tuple(bars)


def _aggregate(minutes: tuple[Candle, ...], interval: Interval) -> list[Candle]:
    size = interval.minutes
    out = []
    for i in range(0, len(minutes), size):
        chunk = minutes[i : i + size]
        out.append(
            Candle(
                timestamp=chunk[0].timestamp,
                open=chunk[0].open,
                high=max(c.high for c in chunk),
                low=min(c.low for c in chunk),
                close=chunk[-1].close,
                volume=sum(c.volume for c in chunk),
            )
        )
    return out


class MockMarketDataProvider(MarketDataProvider):
    source = DataSource.SIMULATED

    def __init__(self, seed: int = 7) -> None:
        self.seed = seed

    def list_instruments(self) -> list[Instrument]:
        return list(_INSTRUMENTS.values())

    def get_candles(
        self, symbol: str, interval: Interval, start: datetime, end: datetime
    ) -> CandleSeries:
        instrument = self.get_instrument(symbol)
        if interval not in SUPPORTED_INTERVALS:
            raise UnsupportedInterval(
                f"mock provider supports {[i.value for i in SUPPORTED_INTERVALS]}"
            )
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start and end must be timezone-aware")
        if instrument.symbol not in _PROFILES:
            raise UnknownInstrument(symbol)

        candles: list[Candle] = []
        day = start.astimezone(IST).date()
        last_day = end.astimezone(IST).date()
        while day <= last_day:
            if is_trading_day(day):
                for candle in _aggregate(_minute_bars(self.seed, instrument.symbol, day), interval):
                    if candle.timestamp >= start and candle.timestamp + interval.delta <= end:
                        candles.append(candle)
            day += timedelta(days=1)
        return CandleSeries(
            instrument=instrument, interval=interval, source=self.source, candles=candles
        )


class MockMacroSource(MacroSource):
    """Simulated factor values (5-minute closes on the NSE grid). Not market data."""

    source = DataSource.SIMULATED

    def __init__(self, seed: int = 7) -> None:
        self.seed = seed

    def points(self, key: str, start: datetime, end: datetime) -> list[MacroPoint]:
        if key not in _MACRO_PROFILES:
            raise UnknownInstrument(key)
        out = []
        day = start.astimezone(IST).date()
        while day <= end.astimezone(IST).date():
            if is_trading_day(day):
                for bar in _aggregate(_minute_bars(self.seed, key, day), Interval.FIVE_MINUTE):
                    close_time = bar.timestamp + Interval.FIVE_MINUTE.delta
                    if start <= close_time <= end:
                        out.append(MacroPoint(timestamp=close_time, value=bar.close))
            day += timedelta(days=1)
        return out
