"""Assembles everything the portal shows: live setups, paper trades, factors, news."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel

from .engine import EngineConfig, EquityPoint, RunResult, Stats, Trade, run, stats
from .macro import FACTORS, FactorSeries, FactorSnapshot, MacroSource, RegimeConfig, RegimeReading, regime_at, snapshot
from .news import NewsDigest, NewsService
from .providers import MarketDataProvider
from .schemas import CandleSeries, DataSource, Interval
from .session import IST, is_market_open, latest_session_day, previous_trading_days, session_bounds
from .strategies import Market, Setup, Strategy, StrategyInfo, default_strategies
from .strategy import StrategyConfig
from .validation import DataIssue, validate_series

WARMUP_SESSIONS = 3
INTERVAL = Interval.FIVE_MINUTE
LIVE_FILTER = True  # the live paper desk trades with the regime filter on

ENGINE_RULES = [
    "A setup is read only after its candle closes; the trade enters at the next candle's open.",
    "New entries from 09:20 to 14:30, one position at a time per strategy, 3-candle cooldown after an exit.",
    "Stop and target are fixed at entry. If one candle touches both, the stop is assumed to fill first.",
    "Open trades are squared off at 15:20. Results are NIFTY points after 0.5 pt slippage each way.",
    "Sessions whose data fails validation (gaps, bad candles) are not traded.",
    "Regime filter: no longs while cross-market risk is RISK_OFF, no shorts while it is RISK_ON.",
]


class PortalCandle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    ema_fast: float | None
    ema_slow: float | None
    vwap: float | None
    rsi: float | None


class LiveStrategy(BaseModel):
    info: StrategyInfo
    state: str  # LONG_SETUP / SHORT_SETUP / WATCHING / NOT_READY / DATA_INVALID
    setup: Setup | None
    position: Trade | None
    today_trades: list[Trade]
    today_points: float
    skipped_today: int


class MacroPanel(BaseModel):
    factors: list[FactorSnapshot]
    regime: RegimeReading
    source: DataSource
    errors: list[str]


class Overview(BaseModel):
    symbol: str
    display_name: str
    source: DataSource
    as_of: datetime
    market_open: bool
    session_day: date
    data_issues: list[DataIssue]
    notes: list[str]
    candles: list[PortalCandle]
    strategies: list[LiveStrategy]
    macro: MacroPanel
    news: NewsDigest
    engine_rules: list[str]
    live_filter: bool


class StrategyRun(BaseModel):
    strategy_id: str
    filter_on: bool
    stats: Stats
    equity: list[EquityPoint]
    trades: list[Trade]


class Performance(BaseModel):
    symbol: str
    source: DataSource
    as_of: datetime
    sessions: list[date]
    skipped_sessions: list[date]
    strategies: list[StrategyInfo]
    runs: list[StrategyRun]
    engine_rules: list[str]
    notes: list[str]


class Catalog(BaseModel):
    strategies: list[StrategyInfo]
    engine_rules: list[str]
    regime: RegimeConfig
    factors: list[dict]
    live_filter: bool


def _notes(source: DataSource) -> list[str]:
    if source is DataSource.SIMULATED:
        return ["SIMULATED prices, volume and factors from a deterministic generator. Not market data."]
    if source is DataSource.PUBLIC_DELAYED:
        return [
            "Prices from Yahoo Finance's public feed: real but delayed and unofficial.",
            "NIFTY 50 has no traded volume, so VWAP is weighted by NIFTYBEES ETF volume (a proxy).",
        ]
    return []


class PortalService:
    def __init__(
        self,
        provider: MarketDataProvider,
        macro: MacroSource,
        news: NewsService,
        strategies: list[Strategy] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.provider = provider
        self.macro = macro
        self.news = news
        self.strategies = strategies or default_strategies()
        self.clock = clock
        self.config = StrategyConfig()
        self.regime_config = RegimeConfig()
        self._pool = ThreadPoolExecutor(max_workers=8)

    # ---- data loading -------------------------------------------------------------------------

    def _as_of(self, as_of: datetime | None) -> datetime:
        if as_of is None:
            return self.clock().astimezone(IST)
        return (as_of if as_of.tzinfo else as_of.replace(tzinfo=IST)).astimezone(IST)

    def _load(self, symbol: str, at: datetime, sessions: int):
        day = latest_session_day(at)
        days = previous_trading_days(day, sessions + WARMUP_SESSIONS)
        start = session_bounds(days[0])[0]
        candles_f = self._pool.submit(self.provider.get_candles, symbol, INTERVAL, start, at)
        factors_f = {f.key: self._pool.submit(self.macro.points, f.key, start - timedelta(days=4), at) for f in FACTORS}
        series: CandleSeries = candles_f.result()  # provider errors propagate to the API layer
        factors, errors = {}, {}
        for key, fut in factors_f.items():
            try:
                factors[key] = FactorSeries(fut.result())
            except Exception as exc:
                errors[key] = f"{type(exc).__name__}: {exc}"[:160]
        return day, days[WARMUP_SESSIONS:], series, factors, errors

    def _valid_days(self, series: CandleSeries, days: list[date], at: datetime) -> tuple[set[date], dict[date, list[DataIssue]]]:
        valid, issues = set(), {}
        for d in days:
            day_series = series.model_copy(
                update={"candles": [c for c in series.candles if c.timestamp.astimezone(IST).date() == d]}
            )
            found = validate_series(day_series, as_of=at if d == latest_session_day(at) else None)
            if found:
                issues[d] = found
            else:
                valid.add(d)
        return valid, issues

    def _run(self, strategy: Strategy, m: Market, valid: set[date], factors: dict, live_day: date | None,
             filter_on: bool) -> RunResult:
        return run(
            strategy, m, valid, INTERVAL,
            regime_fn=lambda t: regime_at(factors, t, self.regime_config),
            config=EngineConfig(use_regime_filter=filter_on),
            live_day=live_day,
        )

    # ---- public views -------------------------------------------------------------------------

    def catalog(self) -> Catalog:
        return Catalog(
            strategies=[s.info for s in self.strategies],
            engine_rules=ENGINE_RULES,
            regime=self.regime_config,
            factors=[{"key": f.key, "label": f.label, "why": f.why, "risk_off_when_rising": f.risk_off_when_rising}
                     for f in FACTORS],
            live_filter=LIVE_FILTER,
        )

    def overview(self, symbol: str = "NIFTY", as_of: datetime | None = None) -> Overview:
        at = self._as_of(as_of)
        news_f = self._pool.submit(self.news.latest)
        day, _, series, factors, factor_errors = self._load(symbol, at, sessions=1)
        live_day = day if is_market_open(at) else None
        valid, issues = self._valid_days(series, [day], at)
        m = Market.build(series, self.config)
        today = [i for i, d in enumerate(m.day) if d == day]

        lives = []
        for s in self.strategies:
            result = self._run(s, m, valid, factors, live_day, LIVE_FILTER)
            todays = [t for t in result.trades if t.entry_time.astimezone(IST).date() == day]
            position = next((t for t in todays if t.exit_reason.value == "OPEN"), None)
            if day not in valid:
                state, setup = "DATA_INVALID", None
            elif not today:
                state, setup = "NOT_READY", None
            else:
                setup = s.setup(m, today[-1])
                state = f"{setup.side.value}_SETUP" if setup.side else ("WATCHING" if setup.long_checks else "NOT_READY")
            lives.append(LiveStrategy(
                info=s.info, state=state, setup=setup, position=position, today_trades=todays,
                today_points=round(sum(t.points for t in todays), 2),
                skipped_today=sum(1 for k in result.skipped if k.time.astimezone(IST).date() == day),
            ))

        rows = [
            PortalCandle(**m.candles[i].model_dump(), ema_fast=m.ema_fast[i], ema_slow=m.ema_slow[i],
                         vwap=m.vwap[i], rsi=m.rsi[i])
            for i in today
        ]
        macro = MacroPanel(
            factors=[snapshot(f, factors.get(f.key), at, factor_errors.get(f.key)) for f in FACTORS],
            regime=regime_at(factors, at, self.regime_config),
            source=self.macro.source,
            errors=[f"{k}: {v}" for k, v in factor_errors.items()],
        )
        return Overview(
            symbol=series.instrument.symbol,
            display_name=series.instrument.display_name,
            source=series.source,
            as_of=at,
            market_open=is_market_open(at),
            session_day=day,
            data_issues=issues.get(day, []),
            notes=_notes(series.source),
            candles=rows,
            strategies=lives,
            macro=macro,
            news=news_f.result(),
            engine_rules=ENGINE_RULES,
            live_filter=LIVE_FILTER,
        )

    def performance(self, symbol: str = "NIFTY", as_of: datetime | None = None, sessions: int = 20) -> Performance:
        at = self._as_of(as_of)
        day, days, series, factors, _ = self._load(symbol, at, sessions)
        live_day = day if is_market_open(at) else None
        valid, issues = self._valid_days(series, days, at)
        m = Market.build(series, self.config)
        runs = []
        for s in self.strategies:
            for filter_on in (False, True):
                result = self._run(s, m, valid, factors, live_day, filter_on)
                st, eq = stats(result)
                runs.append(StrategyRun(strategy_id=s.info.id, filter_on=filter_on, stats=st, equity=eq,
                                        trades=list(reversed(result.trades))))
        return Performance(
            symbol=series.instrument.symbol,
            source=series.source,
            as_of=at,
            sessions=days,
            skipped_sessions=sorted(issues),
            strategies=[s.info for s in self.strategies],
            runs=runs,
            engine_rules=ENGINE_RULES,
            notes=_notes(series.source),
        )
