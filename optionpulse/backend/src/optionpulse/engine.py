"""Paper-trading engine: turns strategy setups into simulated trades.

Rules, identical for every strategy:

* A setup is read on a candle only after it closes. The trade enters at the
  **next** candle's open, so no trade uses information it could not have had.
* Entries only from 09:20 to 14:30 (entry-candle start), only when flat,
  only on sessions whose data passed validation, and not within
  ``cooldown_bars`` of the previous exit.
* Stop and target are fixed at entry. Each later candle is checked against
  them: a gap through either fills at that candle's open; if one candle
  touches both, the **stop** is assumed to have filled first (conservative).
* Anything still open is squared off at the close of the 15:15 candle
  (15:20), or at the session's last candle if data ends earlier on a past day.
  A trade still running in today's live session is reported as OPEN and
  marked to the latest close.
* ``slippage_points`` is charged on entry and on exit. Results are in NIFTY
  index points; multiply by your lot size for rupees. Option premiums are not
  simulated.
* With the regime filter on, long setups are skipped while the cross-market
  regime is RISK_OFF and shorts while it is RISK_ON.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .macro import Regime, RegimeReading
from .schemas import Interval
from .strategies import Market, Side, Strategy

SQUARE_OFF_BAR = 72  # 15:15 candle; exit at its close (15:20)
LAST_ENTRY_BAR = 63  # 14:30 candle


class EngineConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    slippage_points: float = Field(default=0.5, ge=0)
    cooldown_bars: int = Field(default=3, ge=0)
    use_regime_filter: bool = False


class ExitReason(str, Enum):
    TARGET = "TARGET"
    STOP = "STOP"
    SQUARE_OFF = "SQUARE_OFF"
    OPEN = "OPEN"


class Trade(BaseModel):
    id: str
    strategy_id: str
    side: Side
    signal_time: datetime
    entry_time: datetime
    entry_price: float
    stop: float
    target: float
    exit_time: datetime | None
    exit_price: float | None
    exit_reason: ExitReason
    points: float
    r_multiple: float
    bars_held: int
    regime: Regime
    regime_reasons: list[str]


class SkippedSignal(BaseModel):
    time: datetime
    side: Side
    regime: Regime
    reasons: list[str]


class RunResult(BaseModel):
    trades: list[Trade]
    skipped: list[SkippedSignal]


RegimeFn = Callable[[datetime], RegimeReading]


def _unknown(_: datetime) -> RegimeReading:
    return RegimeReading(regime=Regime.UNKNOWN, reasons=["regime not computed"], changes={})


def run(
    strategy: Strategy,
    m: Market,
    valid_days: set[date],
    interval: Interval = Interval.FIVE_MINUTE,
    regime_fn: RegimeFn | None = None,
    config: EngineConfig = EngineConfig(),
    live_day: date | None = None,
) -> RunResult:
    """Simulate ``strategy`` over ``m``. ``live_day`` is a session still in progress."""
    regime_fn = regime_fn or _unknown
    slip = config.slippage_points
    candles = m.candles
    trades: list[Trade] = []
    skipped: list[SkippedSignal] = []
    pos: dict | None = None
    last_exit_index = -10**9
    traded_sides: set[tuple[date, Side]] = set()

    def close(i: int, raw_price: float, reason: ExitReason) -> None:
        nonlocal pos, last_exit_index
        assert pos is not None
        sign = 1 if pos["side"] is Side.LONG else -1
        price = raw_price - sign * slip if reason is not ExitReason.OPEN else raw_price
        points = sign * (price - pos["entry"])
        risk = abs(pos["entry"] - pos["stop"]) or 1e-9
        trades.append(Trade(
            id=f"{strategy.info.id}-{pos['entry_time']:%Y%m%d-%H%M}",
            strategy_id=strategy.info.id,
            side=pos["side"],
            signal_time=pos["signal_time"],
            entry_time=pos["entry_time"],
            entry_price=round(pos["entry"], 2),
            stop=round(pos["stop"], 2),
            target=round(pos["target"], 2),
            exit_time=None if reason is ExitReason.OPEN else candles[i].timestamp + interval.delta,
            exit_price=round(price, 2),
            exit_reason=reason,
            points=round(points, 2),
            r_multiple=round(points / risk, 2),
            bars_held=i - pos["entry_index"] + 1,
            regime=pos["regime"].regime,
            regime_reasons=pos["regime"].reasons,
        ))
        pos = None
        last_exit_index = i

    for i, c in enumerate(candles):
        # 1. Manage an open position on this candle.
        if pos is not None:
            long = pos["side"] is Side.LONG
            stop, target = pos["stop"], pos["target"]
            if (c.open <= stop) if long else (c.open >= stop):
                close(i, c.open, ExitReason.STOP)
            elif (c.low <= stop) if long else (c.high >= stop):
                close(i, stop, ExitReason.STOP)
            elif (c.open >= target) if long else (c.open <= target):
                close(i, c.open, ExitReason.TARGET)
            elif (c.high >= target) if long else (c.low <= target):
                close(i, target, ExitReason.TARGET)
            elif m.bar_of_day[i] >= SQUARE_OFF_BAR:
                close(i, c.close, ExitReason.SQUARE_OFF)
            else:
                last_of_day = i + 1 == len(candles) or m.day[i + 1] != m.day[i]
                if last_of_day and m.day[i] != live_day:
                    close(i, c.close, ExitReason.SQUARE_OFF)
                elif i + 1 == len(candles):
                    close(i, c.close, ExitReason.OPEN)

        # 2. Look for a new entry signalled by this (closed) candle.
        if pos is not None or i + 1 >= len(candles) or m.day[i] not in valid_days:
            continue
        nxt = candles[i + 1]
        if m.day[i + 1] != m.day[i] or nxt.timestamp - c.timestamp != interval.delta:
            continue
        if m.bar_of_day[i + 1] > LAST_ENTRY_BAR or i - last_exit_index <= config.cooldown_bars:
            continue
        setup = strategy.setup(m, i)
        if setup.side is None:
            continue
        if strategy.info.one_trade_per_side_per_day and (m.day[i], setup.side) in traded_sides:
            continue
        reading = regime_fn(c.timestamp + interval.delta)
        if config.use_regime_filter and (
            (setup.side is Side.LONG and reading.regime is Regime.RISK_OFF)
            or (setup.side is Side.SHORT and reading.regime is Regime.RISK_ON)
        ):
            skipped.append(SkippedSignal(time=c.timestamp, side=setup.side, regime=reading.regime,
                                         reasons=reading.reasons))
            continue
        sign = 1 if setup.side is Side.LONG else -1
        entry = nxt.open + sign * slip
        stop, target = strategy.exits(setup.side, entry, m, i)
        if not ((stop < entry < target) if sign > 0 else (target < entry < stop)):
            continue  # e.g. snap-back target already reached at the open
        traded_sides.add((m.day[i], setup.side))
        pos = {"side": setup.side, "entry": entry, "stop": stop, "target": target, "entry_index": i + 1,
               "entry_time": nxt.timestamp, "signal_time": c.timestamp, "regime": reading}
        # The entry candle itself can hit the stop or target; it is handled on the next loop pass.

    return RunResult(trades=trades, skipped=skipped)


class EquityPoint(BaseModel):
    time: datetime
    points: float


class Stats(BaseModel):
    trades: int
    open_trades: int
    wins: int
    losses: int
    win_rate: float | None
    total_points: float
    avg_points: float | None
    avg_r: float | None
    profit_factor: float | None
    max_drawdown: float
    best: float | None
    worst: float | None
    skipped_by_filter: int


def stats(result: RunResult) -> tuple[Stats, list[EquityPoint]]:
    closed = [t for t in result.trades if t.exit_reason is not ExitReason.OPEN]
    wins = [t for t in closed if t.points > 0]
    losses = [t for t in closed if t.points <= 0]
    gross_win = sum(t.points for t in wins)
    gross_loss = -sum(t.points for t in losses)
    equity, cum, peak, dd = [], 0.0, 0.0, 0.0
    for t in sorted(closed, key=lambda t: t.exit_time):
        cum += t.points
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
        equity.append(EquityPoint(time=t.exit_time, points=round(cum, 2)))
    n = len(closed)
    return Stats(
        trades=n,
        open_trades=len(result.trades) - n,
        wins=len(wins),
        losses=len(losses),
        win_rate=round(len(wins) / n * 100, 1) if n else None,
        total_points=round(cum, 2),
        avg_points=round(cum / n, 2) if n else None,
        avg_r=round(sum(t.r_multiple for t in closed) / n, 2) if n else None,
        profit_factor=round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        max_drawdown=round(dd, 2),
        best=max((t.points for t in closed), default=None),
        worst=min((t.points for t in closed), default=None),
        skipped_by_filter=len(result.skipped),
    ), equity
