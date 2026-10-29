from datetime import datetime, timezone

import httpx
import pytest

from optionpulse.providers.yahoo import (
    YahooClient, YahooError, YahooMacroSource, YahooMarketDataProvider, parse_chart,
)
from optionpulse.schemas import DataSource, Interval
from optionpulse.session import IST
from optionpulse.validation import IssueCode, validate_series


def epoch(h, m):
    return int(datetime(2026, 10, 28, h, m, tzinfo=IST).timestamp())


def chart(stamps, rows, error=None):
    if error:
        return {"chart": {"result": None, "error": {"code": "Not Found", "description": error}}}
    cols = list(zip(*rows)) if rows else [[]] * 5
    return {"chart": {"result": [{
        "meta": {"symbol": "^NSEI", "gmtoffset": 19800},
        "timestamp": stamps,
        "indicators": {"quote": [{"open": list(cols[0]), "high": list(cols[1]), "low": list(cols[2]),
                                  "close": list(cols[3]), "volume": list(cols[4])}]},
    }], "error": None}}


INDEX = chart(
    [epoch(9, 15), epoch(9, 20), epoch(9, 25), epoch(9, 30), epoch(9, 32)],
    [
        (25000.12, 25010.4, 24995.0, 25005.333, 0),
        (25005.3, 25004.0, 24990.0, 25000.0, 0),  # high below open: widened
        (None, None, None, None, None),  # Yahoo null bar -> gap
        (25001.0, 25020.0, 25000.0, 25015.0, 0),
        (25015.0, 25016.0, 25014.0, 25015.5, 0),  # live tick, off-grid -> dropped
    ],
)
ETF = chart([epoch(9, 15), epoch(9, 20), epoch(9, 30)], [(1, 1, 1, 1, 5000), (1, 1, 1, 1, 7000), (1, 1, 1, 1, 9000)])


def transport(payloads, calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        sym = request.url.path.rsplit("/", 1)[-1]
        if calls is not None:
            calls.append(sym)
        body = payloads.get(sym)
        return httpx.Response(404, json={}) if body is None else httpx.Response(200, json=body)
    return httpx.MockTransport(handler)


def test_parse_chart_and_errors():
    bars = parse_chart(INDEX)
    assert bars[0].timestamp == datetime(2026, 10, 28, 9, 15, tzinfo=IST)
    assert bars[2].close is None
    with pytest.raises(YahooError, match="No data"):
        parse_chart(chart([], [], error="No data found"))
    with pytest.raises(YahooError):
        parse_chart({"chart": {"result": []}})


def test_provider_normalises_bars():
    client = YahooClient(transport=transport({"^NSEI": INDEX, "NIFTYBEES.NS": ETF}))
    p = YahooMarketDataProvider(client)
    start = datetime(2026, 10, 28, 9, 15, tzinfo=IST)
    s = p.get_candles("NIFTY", Interval.FIVE_MINUTE, start, datetime(2026, 10, 28, 9, 36, tzinfo=IST))
    assert s.source is DataSource.PUBLIC_DELAYED
    assert [c.timestamp.strftime("%H:%M") for c in s.candles] == ["09:15", "09:20", "09:30"]
    assert s.candles[0].close == 25005.33  # rounded to paise
    assert s.candles[1].high == 25005.3  # widened to bound the open
    assert [c.volume for c in s.candles] == [5000, 7000, 9000]  # NIFTYBEES volume proxy
    assert {i.code for i in validate_series(s)} == {IssueCode.GAP}  # the null bar surfaces as a gap


def test_unclosed_bar_is_dropped():
    client = YahooClient(transport=transport({"^NSEI": INDEX, "NIFTYBEES.NS": ETF}))
    s = YahooMarketDataProvider(client).get_candles(
        "NIFTY", Interval.FIVE_MINUTE, datetime(2026, 10, 28, 9, 15, tzinfo=IST), datetime(2026, 10, 28, 9, 33, tzinfo=IST))
    assert s.candles[-1].timestamp.strftime("%H:%M") == "09:20"


def test_missing_etf_volume_means_zero_not_a_guess():
    client = YahooClient(transport=transport({"^NSEI": INDEX}))
    s = YahooMarketDataProvider(client).get_candles(
        "NIFTY", Interval.FIVE_MINUTE, datetime(2026, 10, 28, 9, 15, tzinfo=IST), datetime(2026, 10, 28, 9, 36, tzinfo=IST))
    assert all(c.volume == 0 for c in s.candles)


def test_http_failure_raises_yahoo_error():
    client = YahooClient(transport=transport({}))
    with pytest.raises(YahooError, match="HTTP 404"):
        YahooMarketDataProvider(client).get_candles(
            "NIFTY", Interval.FIVE_MINUTE, datetime(2026, 10, 28, 9, 15, tzinfo=IST), datetime(2026, 10, 28, 10, 0, tzinfo=IST))


def test_responses_are_cached_for_ttl():
    calls, now = [], [1_000_000.0]
    client = YahooClient(transport=transport({"^NSEI": INDEX}, calls), ttl_seconds=60, clock=lambda: now[0])
    start = datetime(2026, 10, 28, 9, 15, tzinfo=IST)
    client.chart("^NSEI", "5m", start)
    client.chart("^NSEI", "5m", start)
    assert calls == ["^NSEI"]
    now[0] += 61
    client.chart("^NSEI", "5m", start)
    assert calls == ["^NSEI", "^NSEI"]


def test_macro_points_stamped_at_bar_close():
    brent = chart([epoch(9, 15), epoch(9, 20)], [(70, 71, 69, 70.5, 0), (70.5, 71, 70, None, 0)])
    src = YahooMacroSource(YahooClient(transport=transport({"BZ=F": brent})))
    pts = src.points("BRENT", datetime(2026, 10, 28, 0, 0, tzinfo=IST), datetime(2026, 10, 28, 12, 0, tzinfo=IST))
    assert [(p.timestamp.strftime("%H:%M"), p.value) for p in pts] == [("09:20", 70.5)]
