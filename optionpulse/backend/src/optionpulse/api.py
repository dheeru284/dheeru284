"""HTTP API. Read-only: there are no order, broker or authentication routes.

Paper trades are computed on the fly from market data; nothing is ever sent to a broker.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import Settings
from .macro import MacroSource
from .news import NewsService
from .portal import Catalog, Overview, Performance, PortalService
from .providers import (
    MarketDataProvider, MockMacroSource, MockMarketDataProvider, UnknownInstrument, UnsupportedInterval,
)
from .providers.yahoo import YahooClient, YahooError, YahooMacroSource, YahooMarketDataProvider
from .schemas import CandleSeries, DataSource, Instrument, Interval
from .session import IST, is_market_open, latest_session_day, previous_trading_days, session_bounds
from .strategy import StrategyConfig, StrategyResult, compute_indicators, evaluate

WARMUP_SESSIONS = 3  # earlier sessions loaded so EMA/RSI are warm at the open
SESSION_CHOICES = 10


class DashboardCandle(BaseModel):
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


class Dashboard(BaseModel):
    instrument: Instrument
    interval: Interval
    source: DataSource
    simulated: bool
    as_of: datetime
    market_open: bool
    session_day: date
    sessions: list[date]
    candles: list[DashboardCandle]
    signal: StrategyResult
    config: StrategyConfig
    disclaimer: str


def _parse_as_of(as_of: datetime | None) -> datetime:
    if as_of is None:
        return datetime.now(timezone.utc).astimezone(IST)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=IST)  # naive input is read as exchange time
    return as_of.astimezone(IST)


def _build_sources(settings: Settings) -> tuple[MarketDataProvider, MacroSource]:
    if settings.provider == "yahoo":
        client = YahooClient()
        return YahooMarketDataProvider(client), YahooMacroSource(client)
    return MockMarketDataProvider(seed=settings.mock_seed), MockMacroSource(seed=settings.mock_seed)


def create_app(
    provider: MarketDataProvider | None = None,
    settings: Settings | None = None,
    portal: PortalService | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    default_provider, macro = _build_sources(settings)
    provider = provider or default_provider
    portal = portal or PortalService(provider, macro, NewsService())
    config = StrategyConfig()

    app = FastAPI(title="OptionPulse AI", version="0.3.0")
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET"], allow_headers=["*"]
    )

    def load(symbol: str, interval: Interval, start: datetime, end: datetime) -> CandleSeries:
        try:
            return provider.get_candles(symbol, interval, start, end)
        except UnknownInstrument:
            raise HTTPException(404, f"unknown instrument {symbol!r}") from None
        except UnsupportedInterval as exc:
            raise HTTPException(422, str(exc)) from None
        except YahooError as exc:
            raise HTTPException(502, f"market data unavailable: {exc}") from None

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "provider": settings.provider,
            "source": provider.source.value,
            "order_placement": "disabled",
        }

    def portal_call(fn, *args):
        try:
            return fn(*args)
        except UnknownInstrument as exc:
            raise HTTPException(404, f"unknown instrument {exc}") from None
        except YahooError as exc:
            raise HTTPException(502, f"market data unavailable: {exc}") from None

    @app.get("/api/portal/catalog")
    def portal_catalog() -> Catalog:
        return portal.catalog()

    @app.get("/api/portal/overview")
    def portal_overview(symbol: str = "NIFTY", as_of: datetime | None = None) -> Overview:
        return portal_call(portal.overview, symbol, as_of)

    @app.get("/api/portal/performance")
    def portal_performance(
        symbol: str = "NIFTY",
        sessions: Annotated[int, Query(ge=1, le=40)] = 20,
        as_of: datetime | None = None,
    ) -> Performance:
        return portal_call(portal.performance, symbol, as_of, sessions)

    @app.get("/api/instruments")
    def instruments() -> list[Instrument]:
        return provider.list_instruments()

    @app.get("/api/candles")
    def candles(
        symbol: str = "NIFTY",
        interval: Interval = Interval.FIVE_MINUTE,
        sessions: Annotated[int, Query(ge=1, le=20)] = 1,
        as_of: datetime | None = None,
    ) -> CandleSeries:
        at = _parse_as_of(as_of)
        first = previous_trading_days(latest_session_day(at), sessions)[0]
        return load(symbol, interval, session_bounds(first)[0], at)

    @app.get("/api/dashboard")
    def dashboard(
        symbol: str = "NIFTY",
        interval: Interval = Interval.FIVE_MINUTE,
        as_of: datetime | None = None,
    ) -> Dashboard:
        at = _parse_as_of(as_of)
        day = latest_session_day(at)
        days = previous_trading_days(day, WARMUP_SESSIONS + 1)
        series = load(symbol, interval, session_bounds(days[0])[0], at)
        ind = compute_indicators(series, config)
        rows = [
            DashboardCandle(
                **c.model_dump(),
                ema_fast=ind.ema_fast[i],
                ema_slow=ind.ema_slow[i],
                vwap=ind.vwap[i],
                rsi=ind.rsi[i],
            )
            for i, c in enumerate(series.candles)
            if c.timestamp.astimezone(IST).date() == day
        ]
        return Dashboard(
            instrument=series.instrument,
            interval=interval,
            source=series.source,
            simulated=series.source is DataSource.SIMULATED,
            as_of=at,
            market_open=is_market_open(at),
            session_day=day,
            sessions=list(reversed(previous_trading_days(latest_session_day(datetime.now(IST)), SESSION_CHOICES))),
            candles=rows,
            signal=evaluate(series, config, as_of=at),
            config=config,
            disclaimer=(
                "SIMULATED data from a deterministic generator. Not market data, not advice. "
                "OptionPulse does not place orders."
                if series.source is DataSource.SIMULATED
                else "Read-only market data. Not advice. OptionPulse does not place orders."
            ),
        )

    return app
