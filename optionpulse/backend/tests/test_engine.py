from datetime import date, timedelta

import pytest

from optionpulse.engine import EngineConfig, ExitReason, run, stats
from optionpulse.macro import Regime, RegimeReading
from optionpulse.schemas import Candle, CandleSeries, DataSource, Interval
from optionpulse.session import bar_starts
from optionpulse.strategies import Market, Setup, Side, Strategy, StrategyInfo

from .conftest import DAY, NIFTY


def candles_from(rows, day=DAY, start_bar=0):
    """rows: (open, high, low, close) tuples on consecutive 5-minute bars."""
    starts = bar_starts(day, Interval.FIVE_MINUTE)[start_bar:]
    return [Candle(timestamp=t, open=o, high=h, low=lo, close=c, volume=100) for t, (o, h, lo, c) in zip(starts, rows)]


def market(candles):
    return Market.build(CandleSeries(instrument=NIFTY, interval=Interval.FIVE_MINUTE,
                                     source=DataSource.SIMULATED, candles=candles))


class Scripted(Strategy):
    """Signals on chosen candle indices with fixed stop/target distances."""

    def __init__(self, signals: dict[int, Side], stop=10.0, target=20.0, once=False):
        self.signals, self.stop, self.target = signals, stop, target
        self.info = StrategyInfo(id="scripted", name="Scripted", style="test", summary="", how_it_works=[],
                                 long_rules=[], short_rules=[], exit_rules=[], parameters={}, works_best="",
                                 struggles="", one_trade_per_side_per_day=once)

    def setup(self, m, i):
        return Setup(side=self.signals.get(i), long_checks=[], short_checks=[])

    def exits(self, side, entry, m, i):
        s = 1 if side is Side.LONG else -1
        return entry - s * self.stop, entry + s * self.target


FLAT = (100.0, 101.0, 99.0, 100.0)
NO_SLIP = EngineConfig(slippage_points=0.0, cooldown_bars=0)


def test_enters_at_next_open_and_hits_target():
    rows = [FLAT, FLAT, (105.0, 106.0, 104.0, 105.0), (105.0, 126.0, 104.0, 125.0)] + [FLAT] * 3
    m = market(candles_from(rows))
    trades = run(Scripted({1: Side.LONG}), m, {DAY}, config=NO_SLIP).trades
    assert len(trades) == 1
    t = trades[0]
    assert t.entry_time == m.candles[2].timestamp and t.entry_price == 105.0
    assert t.exit_reason is ExitReason.TARGET and t.exit_price == 125.0
    assert t.points == 20.0 and t.r_multiple == 2.0


def test_stop_assumed_first_when_both_touched():
    rows = [FLAT, FLAT, (100.0, 125.0, 85.0, 100.0)] + [FLAT] * 3
    t = run(Scripted({1: Side.LONG}), market(candles_from(rows)), {DAY}, config=NO_SLIP).trades[0]
    assert t.exit_reason is ExitReason.STOP and t.points == -10.0


def test_gap_through_stop_fills_at_open():
    rows = [FLAT, FLAT, FLAT, (80.0, 82.0, 79.0, 81.0)] + [FLAT] * 3
    t = run(Scripted({1: Side.LONG}), market(candles_from(rows)), {DAY}, config=NO_SLIP).trades[0]
    assert t.exit_reason is ExitReason.STOP and t.exit_price == 80.0 and t.points == -20.0


def test_short_side_and_slippage():
    rows = [FLAT, FLAT, (100.0, 101.0, 70.0, 75.0)] + [FLAT] * 3
    t = run(Scripted({1: Side.SHORT}), market(candles_from(rows)), {DAY},
            config=EngineConfig(slippage_points=0.5, cooldown_bars=0)).trades[0]
    assert t.entry_price == 99.5  # sold 0.5 below the open
    assert t.target == 79.5 and t.exit_reason is ExitReason.TARGET
    assert t.exit_price == 80.0  # bought back 0.5 above the target
    assert t.points == 19.5


def test_square_off_at_1520():
    rows = [FLAT] * 75
    t = run(Scripted({60: Side.LONG}, stop=50, target=50), market(candles_from(rows)), {DAY}, config=NO_SLIP).trades[0]
    assert t.exit_reason is ExitReason.SQUARE_OFF
    assert t.exit_time.strftime("%H:%M") == "15:20"


def test_no_entries_after_1430():
    rows = [FLAT] * 75
    assert run(Scripted({63: Side.LONG}), market(candles_from(rows)), {DAY}).trades == []
    assert len(run(Scripted({62: Side.LONG}), market(candles_from(rows)), {DAY}).trades) == 1


def test_live_day_leaves_trade_open_and_past_day_squares_off():
    rows = [FLAT] * 10
    m = market(candles_from(rows))
    live = run(Scripted({2: Side.LONG}, stop=50, target=50), m, {DAY}, config=NO_SLIP, live_day=DAY).trades[0]
    assert live.exit_reason is ExitReason.OPEN and live.exit_time is None
    past = run(Scripted({2: Side.LONG}, stop=50, target=50), m, {DAY}, config=NO_SLIP).trades[0]
    assert past.exit_reason is ExitReason.SQUARE_OFF


def test_invalid_day_is_not_traded():
    m = market(candles_from([FLAT] * 10))
    assert run(Scripted({2: Side.LONG}), m, valid_days=set()).trades == []


def test_cooldown_and_one_position_at_a_time():
    rows = [FLAT, FLAT, (100.0, 125.0, 99.0, 120.0)] + [FLAT] * 10
    signals = {i: Side.LONG for i in range(1, 12)}
    trades = run(Scripted(signals), market(candles_from(rows)), {DAY},
                 config=EngineConfig(slippage_points=0, cooldown_bars=3)).trades
    assert trades[0].exit_reason is ExitReason.TARGET  # exits on candle 2
    assert trades[1].signal_time == market(candles_from(rows)).candles[6].timestamp  # 2 + 3 bars cooldown + 1


def test_one_trade_per_side_per_day():
    rows = [FLAT, FLAT, (100.0, 125.0, 99.0, 120.0)] + [FLAT] * 10
    trades = run(Scripted({1: Side.LONG, 8: Side.LONG}, once=True), market(candles_from(rows)), {DAY}, config=NO_SLIP).trades
    assert len(trades) == 1


def test_regime_filter_blocks_against_the_regime():
    m = market(candles_from([FLAT] * 10))
    off = lambda t: RegimeReading(regime=Regime.RISK_OFF, reasons=["Brent +2%"], changes={})
    strat = Scripted({2: Side.LONG, 5: Side.SHORT}, stop=50, target=50)
    plain = run(strat, m, {DAY}, regime_fn=off, config=NO_SLIP)
    assert [t.side for t in plain.trades] == [Side.LONG]  # one position at a time
    assert plain.trades[0].regime is Regime.RISK_OFF  # recorded even with the filter off
    filtered = run(strat, m, {DAY}, regime_fn=off, config=EngineConfig(slippage_points=0, cooldown_bars=0, use_regime_filter=True))
    assert [t.side for t in filtered.trades] == [Side.SHORT]
    assert len(filtered.skipped) == 1 and filtered.skipped[0].side is Side.LONG


def test_no_entry_across_a_gap_in_data():
    c = candles_from([FLAT] * 6)
    m = market(c[:3] + c[4:])
    assert run(Scripted({2: Side.LONG}), m, {DAY}).trades == []


def test_stats():
    rows = [FLAT, FLAT, (100.0, 125.0, 99.0, 120.0), FLAT, FLAT, FLAT, (100.0, 101.0, 85.0, 90.0)] + [FLAT] * 5
    result = run(Scripted({1: Side.LONG, 5: Side.LONG}), market(candles_from(rows)), {DAY}, config=NO_SLIP)
    st, equity = stats(result)
    assert st.trades == 2 and st.wins == 1 and st.losses == 1
    assert st.win_rate == 50.0 and st.total_points == 10.0
    assert st.profit_factor == 2.0 and st.max_drawdown == 10.0
    assert [e.points for e in equity] == [20.0, 10.0]
