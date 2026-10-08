from datetime import date, timedelta

from app.services.price_history import (
    DailyPoint,
    baseline_candidates,
    clip_upper_spikes,
    compute_stats,
    discount_pct,
    select_baseline,
)

TODAY = date(2026, 10, 8)


def series(prices_by_age: dict[int, float]) -> list[DailyPoint]:
    return [DailyPoint(TODAY - timedelta(days=age), p, 3) for age, p in prices_by_age.items()]


def flat(days: int, price: float, start_age: int = 1):
    return {start_age + i: price for i in range(days)}


def test_normal_price_stats():
    pts = series(flat(60, 10000))
    st = compute_stats(pts, TODAY)
    assert st.median == 10000 and st.min_price == st.max_price == 10000
    assert st.quality == "MEDIUM" or st.quality == "HIGH"
    assert st.volatility == 0
    assert st.avg[7] == 10000 and st.med[30] == 10000


def test_fifty_percent_drop_detected_against_median():
    pts = series(flat(60, 10000))
    base = select_baseline(baseline_candidates(pts, TODAY))
    assert base and base[1] == 10000
    assert discount_pct(base[1], 5000) == 50.0


def test_temporary_spike_does_not_inflate_baseline():
    data = flat(60, 10000)
    data[20] = 18000  # one-day spike
    pts = series(data)
    st = compute_stats(pts, TODAY)
    assert st.max_price == 18000 and st.robust_max == 10000
    base = select_baseline(baseline_candidates(pts, TODAY))
    assert base[1] == 10000
    assert discount_pct(base[1], 9000) == 10.0  # NOT 50% off the spike


def test_spec_example_history():
    prices = [10000, 9500, 9200, 8900, 8700, 5000]
    pts = [DailyPoint(TODAY - timedelta(days=i + 1), p, 4) for i, p in enumerate(prices * 4)]
    st = compute_stats(pts, TODAY)
    assert 8000 < st.median <= 9500
    assert discount_pct(st.median, 4400) > 45


def test_outlier_low_price_does_not_move_median():
    data = flat(60, 10000)
    data[10] = 100  # glitch
    st = compute_stats(series(data), TODAY)
    assert st.min_price == 100 and st.median == 10000


def test_clip_upper_spikes_keeps_lows():
    vals = [10000] * 20 + [30000, 100]
    out = clip_upper_spikes(vals)
    assert 30000 not in out and 100 in out


def test_insufficient_history():
    pts = [DailyPoint(TODAY - timedelta(days=i), 10000, 1) for i in range(1, 4)]
    st = compute_stats(pts, TODAY)
    assert st.insufficient and st.quality == "LOW" and "Insufficient price history" in st.notes
    assert baseline_candidates(pts, TODAY) == {}


def test_empty_history():
    st = compute_stats([], TODAY)
    assert st.insufficient and st.n_observations == 0


def test_quality_bands():
    # 100 observations over 90 days -> HIGH
    pts = [DailyPoint(TODAY - timedelta(days=i), 100, 1) for i in range(1, 91)] + []
    pts = [DailyPoint(p.day, p.price, 2) for p in pts]
    assert compute_stats(pts, TODAY).quality == "HIGH"
    # 15 observations over 10 days -> MEDIUM
    pts = [DailyPoint(TODAY - timedelta(days=i), 100, 2) for i in range(1, 9)]
    pts.append(DailyPoint(TODAY - timedelta(days=10), 100, 1))
    assert compute_stats(pts, TODAY).quality == "MEDIUM"
    # 3 observations -> LOW
    assert compute_stats([DailyPoint(TODAY - timedelta(days=i), 100, 1) for i in (1, 2, 3)], TODAY).quality == "LOW"


def test_sustained_new_price_is_not_a_fresh_drop():
    data = {**flat(60, 10000, start_age=40), **flat(39, 5000, start_age=1)}  # low for 39 days
    base = select_baseline(baseline_candidates(series(data), TODAY))
    assert base[0] == "median_30d" and base[1] == 5000
    assert discount_pct(base[1], 5000) == 0


def test_fake_mrp_pattern_not_a_deal():
    # Always ~10,000; MRP of 20,000 is irrelevant to the engine
    base = select_baseline(baseline_candidates(series(flat(60, 10000)), TODAY))
    assert discount_pct(base[1], 9999) < 1
