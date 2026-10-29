"""Cross-market factors (oil, rupee, volatility, global risk) and the risk regime.

A factor is a plain time series of values. Its *day change* at time ``t`` is
measured against the last value recorded before midnight IST of ``t``'s date,
so it means "since yesterday" for every factor regardless of where it trades.

The regime turns three of those changes into RISK_OFF / NEUTRAL / RISK_ON.
The paper-trading engine can use it as a filter: no longs while RISK_OFF, no
shorts while RISK_ON. Performance is reported with and without the filter so
its effect is visible rather than assumed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import Enum

from pydantic import BaseModel, ConfigDict

from .schemas import DataSource
from .session import IST


@dataclass(frozen=True)
class Factor:
    key: str
    label: str
    unit: str
    why: str
    risk_off_when_rising: bool | None  # None: shown for context only


FACTORS: tuple[Factor, ...] = (
    Factor("BRENT", "Brent crude", "USD/bbl",
           "India imports most of its crude. Pricier oil widens the trade deficit, "
           "feeds inflation and usually weighs on NIFTY, especially OMCs, paints and airlines.", True),
    Factor("WTI", "WTI crude", "USD/bbl", "US crude benchmark; confirms what Brent is doing.", True),
    Factor("USDINR", "USD / INR", "₹",
           "A weaker rupee (USD/INR up) tends to go with foreign selling of Indian equities.", True),
    Factor("INDIAVIX", "India VIX", "pts",
           "The market's expected 30-day NIFTY volatility. Spikes mark fear; falling VIX is calm.", True),
    Factor("GOLD", "Gold", "USD/oz", "Safe-haven demand. Context only.", None),
    Factor("SPX_FUT", "S&P 500 futures", "pts",
           "US risk appetite, which often sets the tone for the Indian open.", False),
    Factor("US10Y", "US 10Y yield", "%",
           "Higher US yields pull money out of emerging markets such as India.", True),
)
FACTOR_KEYS = tuple(f.key for f in FACTORS)
REGIME_KEYS = ("BRENT", "INDIAVIX", "USDINR")
_EPSILON = timedelta(microseconds=1)


class MacroPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    value: float


class MacroSource(ABC):
    source: DataSource

    @abstractmethod
    def points(self, key: str, start: datetime, end: datetime) -> list[MacroPoint]:
        """Values for ``key`` with timestamps in ``[start, end]``, oldest first."""


class FactorSeries:
    """A sorted series with O(log n) as-of lookups."""

    def __init__(self, points: Sequence[MacroPoint]) -> None:
        self.points = sorted(points, key=lambda p: p.timestamp)
        self._times = [p.timestamp for p in self.points]

    def value_at(self, t: datetime) -> float | None:
        i = bisect_right(self._times, t)
        return self.points[i - 1].value if i else None

    def reference_at(self, t: datetime) -> float | None:
        midnight = datetime.combine(t.astimezone(IST).date(), time(0, 0), tzinfo=IST)
        i = bisect_right(self._times, midnight - _EPSILON)
        return self.points[i - 1].value if i else None

    def change_pct_at(self, t: datetime) -> float | None:
        now, ref = self.value_at(t), self.reference_at(t)
        if now is None or ref is None or ref == 0:
            return None
        return (now / ref - 1.0) * 100.0

    def session_values(self, t: datetime) -> list[float]:
        """Values since midnight IST of ``t``'s date up to ``t`` (for sparklines)."""
        midnight = datetime.combine(t.astimezone(IST).date(), time(0, 0), tzinfo=IST)
        lo, hi = bisect_right(self._times, midnight - _EPSILON), bisect_right(self._times, t)
        return [p.value for p in self.points[lo:hi]]


class Regime(str, Enum):
    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"
    UNKNOWN = "UNKNOWN"


class RegimeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    brent_risk_off_pct: float = 1.5
    brent_risk_on_pct: float = -1.5
    vix_risk_off_pct: float = 5.0
    vix_risk_on_pct: float = -4.0
    usdinr_risk_off_pct: float = 0.3
    usdinr_risk_on_pct: float = -0.2


class RegimeReading(BaseModel):
    regime: Regime
    reasons: list[str]
    changes: dict[str, float | None]


def regime_at(series: dict[str, FactorSeries], t: datetime, config: RegimeConfig = RegimeConfig()) -> RegimeReading:
    changes = {k: (series[k].change_pct_at(t) if k in series else None) for k in REGIME_KEYS}
    rules = (
        ("BRENT", "Brent", config.brent_risk_off_pct, config.brent_risk_on_pct),
        ("INDIAVIX", "India VIX", config.vix_risk_off_pct, config.vix_risk_on_pct),
        ("USDINR", "USD/INR", config.usdinr_risk_off_pct, config.usdinr_risk_on_pct),
    )
    off, on = [], []
    for key, label, off_at, on_at in rules:
        chg = changes[key]
        if chg is None:
            continue
        if chg >= off_at:
            off.append(f"{label} {chg:+.2f}% (≥ {off_at:+g}%)")
        elif chg <= on_at:
            on.append(f"{label} {chg:+.2f}% (≤ {on_at:+g}%)")
    if all(v is None for v in changes.values()):
        return RegimeReading(regime=Regime.UNKNOWN, reasons=["no factor data"], changes=changes)
    if off and not on:
        return RegimeReading(regime=Regime.RISK_OFF, reasons=off, changes=changes)
    if on and not off:
        return RegimeReading(regime=Regime.RISK_ON, reasons=on, changes=changes)
    reasons = off + on or ["no factor beyond its threshold"]
    return RegimeReading(regime=Regime.NEUTRAL, reasons=reasons, changes=changes)


class FactorSnapshot(BaseModel):
    key: str
    label: str
    unit: str
    why: str
    risk_off_when_rising: bool | None
    value: float | None
    change_pct: float | None
    sparkline: list[float]
    error: str | None = None


def snapshot(factor: Factor, series: FactorSeries | None, t: datetime, error: str | None = None) -> FactorSnapshot:
    return FactorSnapshot(
        key=factor.key,
        label=factor.label,
        unit=factor.unit,
        why=factor.why,
        risk_off_when_rising=factor.risk_off_when_rising,
        value=series.value_at(t) if series else None,
        change_pct=series.change_pct_at(t) if series else None,
        sparkline=series.session_values(t)[-120:] if series else [],
        error=error,
    )
