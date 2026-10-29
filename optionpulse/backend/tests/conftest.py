from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pytest

from optionpulse.schemas import Candle, CandleSeries, DataSource, Exchange, Instrument, InstrumentType, Interval
from optionpulse.session import bar_starts

NIFTY = Instrument(
    symbol="NIFTY",
    display_name="NIFTY 50",
    exchange=Exchange.NSE,
    instrument_type=InstrumentType.INDEX,
    tick_size=0.05,
    lot_size=1,
)
DAY = date(2026, 10, 28)  # a Wednesday


def make_series(
    closes: Sequence[float],
    volumes: Sequence[int] | None = None,
    day: date = DAY,
    interval: Interval = Interval.FIVE_MINUTE,
) -> CandleSeries:
    """Aligned, contiguous candles from ``day``'s open; open = previous close."""
    starts = bar_starts(day, interval)
    assert len(closes) <= len(starts), "keep test series inside one session"
    volumes = volumes if volumes is not None else [1000] * len(closes)
    candles = []
    prev = closes[0]
    for ts, close, vol in zip(starts, closes, volumes):
        candles.append(
            Candle(timestamp=ts, open=prev, high=max(prev, close) + 1, low=min(prev, close) - 1, close=close, volume=vol)
        )
        prev = close
    return CandleSeries(instrument=NIFTY, interval=interval, source=DataSource.SIMULATED, candles=candles)


def zigzag(start: float, up: float, down: float, n: int) -> list[float]:
    """Alternate +up / -down moves, ending on an up move when n is even."""
    out = [start]
    for i in range(1, n):
        out.append(out[-1] + (up if i % 2 == 1 else -down))
    return out


@pytest.fixture
def nifty() -> Instrument:
    return NIFTY
