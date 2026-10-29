from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from optionpulse.api import create_app
from optionpulse.config import Settings
from optionpulse.news import NewsService
from optionpulse.portal import PortalService
from optionpulse.providers import MockMacroSource, MockMarketDataProvider
from optionpulse.providers.yahoo import YahooError

from .test_news import GOOGLE


def offline_news():
    return NewsService(feeds=(("Sample", "x"),), fetch=lambda url: GOOGLE)


@pytest.fixture(scope="module")
def client():
    portal = PortalService(MockMarketDataProvider(), MockMacroSource(), offline_news())
    return TestClient(create_app(settings=Settings(), portal=portal))


def test_catalog(client):
    body = client.get("/api/portal/catalog").json()
    assert [s["id"] for s in body["strategies"]] == ["trend_pulse", "orb", "vwap_snapback"]
    assert body["engine_rules"] and body["live_filter"] is True
    assert {f["key"] for f in body["factors"]} >= {"BRENT", "USDINR", "INDIAVIX"}


def test_overview_midday(client):
    body = client.get("/api/portal/overview", params={"as_of": "2026-10-28T13:00:00+05:30"}).json()
    assert body["source"] == "SIMULATED" and any("SIMULATED" in n for n in body["notes"])
    assert body["market_open"] is True and len(body["candles"]) == 45
    assert len(body["strategies"]) == 3
    for s in body["strategies"]:
        assert s["state"] in {"LONG_SETUP", "SHORT_SETUP", "WATCHING", "NOT_READY", "DATA_INVALID"}
        for t in s["today_trades"]:
            assert t["entry_time"] < "2026-10-28T13:00"
    assert len(body["macro"]["factors"]) == 7
    assert body["macro"]["regime"]["regime"] in {"RISK_ON", "NEUTRAL", "RISK_OFF"}
    assert body["news"]["items"][0]["title"]


def test_overview_is_deterministic(client):
    params = {"as_of": "2026-10-28T13:00:00+05:30"}
    a = client.get("/api/portal/overview", params=params).json()
    b = client.get("/api/portal/overview", params=params).json()
    assert a["strategies"] == b["strategies"] and a["macro"] == b["macro"]


def test_performance(client):
    body = client.get("/api/portal/performance", params={"as_of": "2026-10-28T15:30:00+05:30", "sessions": 10}).json()
    assert len(body["sessions"]) == 10 and body["skipped_sessions"] == []
    assert len(body["runs"]) == 6  # three strategies, filter off and on
    for run in body["runs"]:
        st = run["stats"]
        assert st["trades"] == st["wins"] + st["losses"]
        assert st["open_trades"] == 0  # market closed: everything squared off
        if run["filter_on"] is False:
            assert st["skipped_by_filter"] == 0
        assert all("2026-10-15" <= t["entry_time"][:10] <= "2026-10-28" for t in run["trades"])


def test_performance_bounds(client):
    assert client.get("/api/portal/performance", params={"sessions": 0}).status_code == 422
    assert client.get("/api/portal/performance", params={"sessions": 41}).status_code == 422


def test_feed_outage_is_a_502_not_a_crash():
    class Down(MockMarketDataProvider):
        def get_candles(self, *a, **k):
            raise YahooError("^NSEI: HTTP 429")

    portal = PortalService(Down(), MockMacroSource(), offline_news())
    c = TestClient(create_app(settings=Settings(), portal=portal))
    r = c.get("/api/portal/overview")
    assert r.status_code == 502 and "HTTP 429" in r.json()["detail"]
