import pytest
from fastapi.testclient import TestClient

from optionpulse.api import create_app
from optionpulse.config import Settings


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(settings=Settings()))


def test_health_reports_simulated_and_no_orders(client):
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "provider": "mock", "source": "SIMULATED", "order_placement": "disabled"}


def test_only_read_routes(client):
    methods = {m for route in client.app.routes for m in getattr(route, "methods", set())}
    assert methods <= {"GET", "HEAD"}
    api_paths = {route.path for route in client.app.routes if route.path.startswith("/api")}
    assert api_paths == {
        "/api/health", "/api/instruments", "/api/candles", "/api/dashboard",
        "/api/portal/catalog", "/api/portal/overview", "/api/portal/performance",
    }


def test_instruments(client):
    symbols = {i["symbol"] for i in client.get("/api/instruments").json()}
    assert "NIFTY" in symbols


def test_dashboard_full_session(client):
    r = client.get("/api/dashboard", params={"as_of": "2026-10-28T15:30:00+05:30"})
    assert r.status_code == 200
    body = r.json()
    assert body["simulated"] is True and body["source"] == "SIMULATED"
    assert "SIMULATED" in body["disclaimer"]
    assert body["session_day"] == "2026-10-28"
    assert len(body["candles"]) == 75
    # Warm-up sessions mean indicators are defined from the first displayed bar.
    first = body["candles"][0]
    assert None not in (first["ema_fast"], first["ema_slow"], first["rsi"], first["vwap"])
    assert body["signal"]["signal"] in {"LONG_SETUP", "SHORT_SETUP", "NO_TRADE"}
    assert body["market_open"] is False


def test_dashboard_is_deterministic(client):
    params = {"as_of": "2026-10-28T11:02:00+05:30"}
    a, b = client.get("/api/dashboard", params=params).json(), client.get("/api/dashboard", params=params).json()
    a.pop("sessions"), b.pop("sessions")
    assert a == b
    assert a["market_open"] is True
    assert a["candles"][-1]["timestamp"] == "2026-10-28T10:55:00+05:30"


def test_naive_as_of_is_exchange_time(client):
    body = client.get("/api/dashboard", params={"as_of": "2026-10-28T10:00:00"}).json()
    assert body["candles"][-1]["timestamp"] == "2026-10-28T09:55:00+05:30"


def test_before_first_candle_is_data_invalid(client):
    body = client.get("/api/dashboard", params={"as_of": "2026-10-28T09:17:00+05:30"}).json()
    assert body["candles"] == []
    assert body["signal"]["signal"] == "DATA_INVALID"


def test_candles_endpoint(client):
    body = client.get("/api/candles", params={"as_of": "2026-10-28T15:30:00+05:30", "sessions": 2}).json()
    assert body["source"] == "SIMULATED" and len(body["candles"]) == 150


def test_errors(client):
    assert client.get("/api/dashboard", params={"symbol": "XYZ"}).status_code == 404
    assert client.get("/api/dashboard", params={"interval": "TEN_MINUTE"}).status_code == 422
    assert client.get("/api/dashboard", params={"interval": "BOGUS"}).status_code == 422


def test_settings_default_to_live_yahoo(monkeypatch):
    monkeypatch.delenv("OPTIONPULSE_PROVIDER", raising=False)
    assert Settings.from_env().provider == "yahoo"


def test_settings_refuse_unavailable_provider(monkeypatch):
    monkeypatch.setenv("OPTIONPULSE_PROVIDER", "angelone")
    with pytest.raises(ValueError):
        Settings.from_env()
