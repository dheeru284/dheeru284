"""Robust price-history statistics computed from DAILY prices (not raw crawl rows), so that
crawl frequency cannot bias the statistics. MRP / strike-through prices never enter here."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date

WINDOWS = (7, 30, 90, 180, 365)
BASELINE_WINDOWS = (30, 90, 180, 365)  # + lifetime
# minimum number of distinct days with data inside a window for it to be a credible baseline
MIN_DAYS_IN_WINDOW = {30: 10, 90: 20, 180: 30, 365: 45}
MIN_DAYS_LIFETIME = 14


@dataclass(frozen=True)
class DailyPoint:
    day: date
    price: float
    obs_count: int = 1


@dataclass
class HistoryStats:
    n_observations: int = 0
    n_days: int = 0
    span_days: int = 0
    min_price: float | None = None
    max_price: float | None = None  # raw (may be a spike)
    robust_max: float | None = None  # spike-clipped
    average: float | None = None  # spike-clipped
    median: float | None = None  # lifetime
    avg: dict[int, float] = field(default_factory=dict)  # window -> mean
    med: dict[int, float] = field(default_factory=dict)  # window -> median (30/90/180) + 0 == lifetime
    volatility: float | None = None  # coefficient of variation of spike-clipped prices
    quality: str = "LOW"
    insufficient: bool = True
    notes: list[str] = field(default_factory=list)

    def window_range(self, days: int, points: list[DailyPoint], today: date) -> tuple[float, float] | None:
        vals = [p.price for p in points if 0 <= (today - p.day).days <= days]
        return (min(vals), max(vals)) if vals else None


def median(values: list[float]) -> float:
    return float(statistics.median(values))


def clip_upper_spikes(values: list[float]) -> list[float]:
    """Drop isolated unusually HIGH prices (median + 5 robust-sigma). Low prices are kept - they
    are the signal we are looking for. Scale has a floor so constant series are not over-trimmed."""
    if len(values) < 5:
        return list(values)
    med = median(values)
    mad = median([abs(v - med) for v in values])
    scale = max(1.4826 * mad, 0.02 * med)
    kept = [v for v in values if v <= med + 5 * scale]
    return kept or list(values)


def classify_quality(n_obs: int, n_days: int, span_days: int, min_obs: int = 10) -> str:
    if n_obs < min_obs or n_days < 5:
        return "LOW"
    if n_obs >= 50 and span_days >= 60 and n_days >= 30:
        return "HIGH"
    if span_days >= 7:
        return "MEDIUM"
    return "LOW"


def compute_stats(points: list[DailyPoint], today: date, min_obs: int = 10) -> HistoryStats:
    st = HistoryStats()
    if not points:
        st.notes.append("Insufficient price history")
        return st
    pts = sorted(points, key=lambda p: p.day)
    prices = [p.price for p in pts]
    st.n_observations = sum(p.obs_count for p in pts)
    st.n_days = len({p.day for p in pts})
    st.span_days = (today - pts[0].day).days
    st.min_price, st.max_price = min(prices), max(prices)
    clipped = clip_upper_spikes(prices)
    st.robust_max = max(clipped)
    st.average = statistics.fmean(clipped)
    st.median = median(prices)
    st.med[0] = st.median
    if st.average:
        st.volatility = statistics.pstdev(clipped) / st.average if len(clipped) > 1 else 0.0
    for w in WINDOWS:
        vals = [p.price for p in pts if 0 <= (today - p.day).days <= w]
        if vals:
            st.avg[w] = statistics.fmean(vals)
            if w in BASELINE_WINDOWS or w == 365:
                st.med[w] = median(vals)
    st.quality = classify_quality(st.n_observations, st.n_days, st.span_days, min_obs)
    st.insufficient = st.n_observations < min_obs
    if st.insufficient:
        st.notes.append("Insufficient price history")
    return st


def baseline_candidates(points: list[DailyPoint], today: date) -> dict[str, float]:
    """Credible baselines from history strictly BEFORE today (the current price is excluded).
    A window is only used if it has enough distinct days of data."""
    prior = [p for p in points if p.day < today]
    out: dict[str, float] = {}
    for w in BASELINE_WINDOWS:
        vals = [p.price for p in prior if (today - p.day).days <= w]
        if len({p.day for p in prior if (today - p.day).days <= w}) >= MIN_DAYS_IN_WINDOW[w]:
            out[f"median_{w}d"] = median(vals)
    if len({p.day for p in prior}) >= MIN_DAYS_LIFETIME:
        out["median_lifetime"] = median([p.price for p in prior])
    return out


def select_baseline(candidates: dict[str, float]) -> tuple[str, float] | None:
    """Conservative: the LOWEST credible median. A price that has been low for weeks is the new
    normal (fails the 30-day median), and a one-off spike can't inflate a median."""
    if not candidates:
        return None
    label = min(candidates, key=lambda k: candidates[k])
    return label, candidates[label]


def discount_pct(baseline: float | None, current: float) -> float | None:
    if not baseline or baseline <= 0:
        return None
    return (baseline - current) / baseline * 100.0


def trend_pct(current: float, window_avg: float | None) -> float | None:
    """Current price relative to the window's average (negative == cheaper than usual)."""
    if not window_avg:
        return None
    return (current - window_avg) / window_avg * 100.0
