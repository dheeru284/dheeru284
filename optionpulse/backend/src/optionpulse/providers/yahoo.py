"""Real (delayed) prices from Yahoo Finance's public chart endpoint.

This is an unofficial, keyless endpoint intended for personal use. It can be
delayed, rate-limited or changed without notice, and Yahoo's terms restrict
redistribution, so treat it as a stop-gap until the Angel One SmartAPI
provider (Phase 3). Everything it returns is labelled ``PUBLIC_DELAYED``.

Normalisation applied to every bar, in this order:
1. drop bars with a missing open/high/low/close (Yahoo emits nulls);
2. keep only bars that start on the NSE five-minute grid inside the session
   (drops Yahoo's trailing "live tick" bar and any 15:30 closing print);
3. drop bars that have not closed by ``end``;
4. widen high/low to bound open/close (Yahoo's float rounding can break this
   by a fraction of a point);
5. NIFTY 50 has no traded volume, so each bar's volume is taken from the
   NIFTYBEES ETF bar with the same timestamp (0 if missing). VWAP is
   therefore an ETF-volume-weighted proxy, and is labelled as such.

A dropped bar becomes a gap, which validation reports and the strategies
answer with ``DATA_INVALID`` rather than trading on a hole.
"""

from __future__ import annotations

import threading
import time as _time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from ..macro import MacroPoint, MacroSource
from ..schemas import Candle, CandleSeries, DataSource, Exchange, Instrument, InstrumentType, Interval
from ..session import IST, is_aligned
from .base import MarketDataProvider, UnknownInstrument, UnsupportedInterval

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) OptionPulse/0.3 personal-dashboard"

INDEX_SYMBOLS = {  # canonical -> (index ticker, ETF ticker used for volume)
    "NIFTY": ("^NSEI", "NIFTYBEES.NS"),
    "BANKNIFTY": ("^NSEBANK", "BANKBEES.NS"),
}
MACRO_SYMBOLS = {
    "BRENT": "BZ=F",
    "WTI": "CL=F",
    "USDINR": "INR=X",
    "INDIAVIX": "^INDIAVIX",
    "GOLD": "GC=F",
    "SPX_FUT": "ES=F",
    "US10Y": "^TNX",
}
_YAHOO_INTERVALS = {Interval.FIVE_MINUTE: "5m", Interval.FIFTEEN_MINUTE: "15m"}
MAX_INTRADAY_LOOKBACK = timedelta(days=59)  # Yahoo serves 5m/15m bars for ~60 days

_INSTRUMENTS = {
    "NIFTY": Instrument(symbol="NIFTY", display_name="NIFTY 50", exchange=Exchange.NSE,
                        instrument_type=InstrumentType.INDEX, tick_size=0.05, lot_size=1),
    "BANKNIFTY": Instrument(symbol="BANKNIFTY", display_name="NIFTY BANK", exchange=Exchange.NSE,
                            instrument_type=InstrumentType.INDEX, tick_size=0.05, lot_size=1),
}


class YahooError(RuntimeError):
    pass


@dataclass(frozen=True)
class YahooBar:
    timestamp: datetime
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None


def parse_chart(payload: dict) -> list[YahooBar]:
    """Parse a ``/v8/finance/chart`` response into bars (timestamps are bar starts)."""
    chart = payload.get("chart") or {}
    if chart.get("error"):
        err = chart["error"]
        raise YahooError(f"{err.get('code', 'error')}: {err.get('description', '')}".strip())
    results = chart.get("result") or []
    if not results:
        raise YahooError("response has no result")
    result = results[0]
    stamps = result.get("timestamp") or []
    quotes = (result.get("indicators") or {}).get("quote") or [{}]
    q = quotes[0]
    cols = {k: q.get(k) or [None] * len(stamps) for k in ("open", "high", "low", "close", "volume")}
    bars = []
    for i, ts in enumerate(stamps):
        vol = cols["volume"][i]
        bars.append(
            YahooBar(
                timestamp=datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST),
                open=cols["open"][i],
                high=cols["high"][i],
                low=cols["low"][i],
                close=cols["close"][i],
                volume=int(vol) if vol is not None else None,
            )
        )
    return bars


class YahooClient:
    """Thin cached HTTP client. Responses are reused for ``ttl_seconds``."""

    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        ttl_seconds: float = 60.0,
        clock: Callable[[], float] = _time.time,
    ) -> None:
        self._http = httpx.Client(
            timeout=8.0, headers={"User-Agent": USER_AGENT}, transport=transport, follow_redirects=True
        )
        self._ttl = ttl_seconds
        self._clock = clock
        self._cache: dict[tuple, tuple[float, list[YahooBar]]] = {}
        self._lock = threading.Lock()

    def chart(self, symbol: str, interval: str, start: datetime) -> list[YahooBar]:
        period1 = int(start.timestamp()) // 86_400 * 86_400  # day-floored so the cache key is stable
        key = (symbol, interval, period1)
        now = self._clock()
        with self._lock:
            hit = self._cache.get(key)
            if hit and hit[0] > now:
                return hit[1]
        try:
            resp = self._http.get(
                CHART_URL.format(symbol=symbol),
                params={"interval": interval, "period1": period1, "period2": int(now) + 60,
                        "includePrePost": "false"},
            )
        except httpx.HTTPError as exc:
            raise YahooError(f"{symbol}: {type(exc).__name__}: {exc}") from None
        if resp.status_code != 200:
            raise YahooError(f"{symbol}: HTTP {resp.status_code}")
        try:
            bars = parse_chart(resp.json())
        except ValueError as exc:
            raise YahooError(f"{symbol}: unreadable response ({exc})") from None
        with self._lock:
            self._cache[key] = (now + self._ttl, bars)
        return bars


def _round(v: float) -> float:
    return round(v, 2)


class YahooMarketDataProvider(MarketDataProvider):
    source = DataSource.PUBLIC_DELAYED

    def __init__(self, client: YahooClient | None = None) -> None:
        self.client = client or YahooClient()

    def list_instruments(self) -> list[Instrument]:
        return list(_INSTRUMENTS.values())

    def get_candles(self, symbol: str, interval: Interval, start: datetime, end: datetime) -> CandleSeries:
        instrument = self.get_instrument(symbol)
        if interval not in _YAHOO_INTERVALS:
            raise UnsupportedInterval(f"Yahoo provider supports {[i.value for i in _YAHOO_INTERVALS]}")
        start = max(start, end - MAX_INTRADAY_LOOKBACK)
        index_ticker, etf_ticker = INDEX_SYMBOLS[instrument.symbol]
        yi = _YAHOO_INTERVALS[interval]
        bars = self.client.chart(index_ticker, yi, start)
        try:
            etf_volume = {b.timestamp: b.volume or 0 for b in self.client.chart(etf_ticker, yi, start)}
        except YahooError:
            etf_volume = {}  # VWAP becomes unavailable -> DATA_INVALID, never a guess

        candles = []
        for b in bars:
            if None in (b.open, b.high, b.low, b.close):
                continue
            if not is_aligned(b.timestamp, interval):
                continue
            if b.timestamp < start or b.timestamp + interval.delta > end:
                continue
            o, c = _round(b.open), _round(b.close)
            candles.append(
                Candle(
                    timestamp=b.timestamp,
                    open=o,
                    high=max(_round(b.high), o, c),
                    low=min(_round(b.low), o, c),
                    close=c,
                    volume=etf_volume.get(b.timestamp, 0),
                )
            )
        return CandleSeries(instrument=instrument, interval=interval, source=self.source, candles=candles)


class YahooMacroSource(MacroSource):
    """Factor values from Yahoo: each 5-minute bar's close, stamped at the bar's end."""

    source = DataSource.PUBLIC_DELAYED

    def __init__(self, client: YahooClient | None = None) -> None:
        self.client = client or YahooClient()

    def points(self, key: str, start: datetime, end: datetime) -> list[MacroPoint]:
        if key not in MACRO_SYMBOLS:
            raise UnknownInstrument(key)
        out = []
        for b in self.client.chart(MACRO_SYMBOLS[key], "5m", max(start, end - MAX_INTRADAY_LOOKBACK)):
            close_time = b.timestamp + timedelta(minutes=5)
            if b.close is not None and start <= close_time <= end:
                out.append(MacroPoint(timestamp=close_time, value=b.close))
        return out
