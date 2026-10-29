from optionpulse.strategies import Market, OpeningRangeBreakout, Side, TrendPulse, VwapSnapBack, default_strategies
from optionpulse.strategy import Signal, evaluate

from .conftest import make_series, zigzag


def test_trend_pulse_agrees_with_dashboard_evaluate():
    series = make_series(zigzag(25000, 3, 1.5, 40))
    m = Market.build(series)
    assert evaluate(series).signal is Signal.LONG_SETUP
    assert TrendPulse().setup(m, len(series.candles) - 1).side is Side.LONG
    down = make_series(zigzag(25000, -3, -1.5, 40))
    assert TrendPulse().setup(Market.build(down), 39).side is Side.SHORT


def test_orb_fresh_breakout_long_and_short():
    closes = [100.0, 101.0, 100.5] + [100.8] * 3 + [104.0, 105.0]
    m = Market.build(make_series(closes))
    orb = OpeningRangeBreakout()
    hi, lo = orb._range(m, 6)
    assert orb.setup(m, 5).side is None  # still inside the range
    assert orb.setup(m, 6).side is Side.LONG  # first close above the range high
    assert orb.setup(m, 7).side is None  # not fresh any more
    stop, target = orb.exits(Side.LONG, 104.5, m, 6)
    assert lo <= stop < 104.5 and target - 104.5 == 2 * (104.5 - stop)

    closes = [100.0, 99.0, 99.5] + [99.2] * 3 + [96.0]
    m = Market.build(make_series(closes))
    assert orb.setup(m, 6).side is Side.SHORT


def test_orb_waits_for_range_and_respects_cutoff():
    m = Market.build(make_series([100.0] * 60))
    orb = OpeningRangeBreakout()
    assert "forming" in orb.setup(m, 2).note
    assert "13:00" in orb.setup(m, 50).note


def test_snapback_needs_stretch_rsi_and_reversal():
    # Flat morning, then a sharp sell-off, then one green candle.
    closes = [100.0 + (0.3 if i % 2 else -0.3) for i in range(20)] + [99 - 1.5 * k for k in range(1, 9)] + [87.5]
    series = make_series(closes)
    m = Market.build(series)
    i = len(closes) - 1
    setup = VwapSnapBack().setup(m, i)
    assert {c.name: c.passed for c in setup.long_checks} == {"stretch": True, "rsi": True, "reversal": True}
    assert setup.side is Side.LONG
    stop, target = VwapSnapBack().exits(Side.LONG, 87.6, m, i)
    assert stop < 87.6 < target == m.vwap[i]
    assert VwapSnapBack().setup(m, i - 1).side is None  # red candle: no reversal yet


def test_snapback_outside_window():
    m = Market.build(make_series([100.0] * 70))
    assert "09:45" in VwapSnapBack().setup(m, 3).note


def test_catalog_has_unique_documented_strategies():
    infos = [s.info for s in default_strategies()]
    assert len({i.id for i in infos}) == len(infos) == 3
    for info in infos:
        assert info.long_rules and info.short_rules and info.exit_rules and info.how_it_works
