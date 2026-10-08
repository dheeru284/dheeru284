import logging

import httpx
import pytest

from app.config.settings import Settings
from app.models.price import ExchangeRate
from app.utils import currency
from app.utils.logging import JsonFormatter, redact
from app.utils.normalization import parse_price


def test_settings_env_aliases_and_defaults(monkeypatch):
    monkeypatch.setenv("ALERT_MIN_DISCOUNT", "60")
    monkeypatch.setenv("ALERT_MIN_REVIEWS", "5")
    monkeypatch.setenv("MIN_RATING", "4.2")
    s = Settings(_env_file=None)
    assert (s.min_discount_percent, s.min_review_count, s.min_rating) == (60.0, 5, 4.2)
    assert Settings(_env_file=None, min_discount_percent=50).min_discount_percent == 50
    monkeypatch.setenv("ENABLE_AMAZON", "false")
    assert not Settings(_env_file=None).retailer_enabled("amazon")


def test_parse_price():
    assert parse_price("₹1,29,999.00") == 129999.0 and parse_price("Rs. 499") == 499 and parse_price("free") is None
    assert parse_price("1.299,50") == 1299.5


def test_secrets_are_redacted_in_logs():
    msg = ("webhook https://hooks.slack.com/services/T000/B000/SECRETVALUE token=xoxb-123-abc "
           "postgresql://user:hunter2@db/x api_key: abcdef")
    out = redact(msg)
    for leaked in ("SECRETVALUE", "xoxb-123", "hunter2", "abcdef"):
        assert leaked not in out
    rec = logging.LogRecord("t", logging.INFO, "", 0, "hello %s", ("https://hooks.slack.com/services/A/B/C",), None)
    rec.url = "https://hooks.slack.com/services/A/B/C"
    assert "services/A/B/C" not in JsonFormatter().format(rec)


def test_fx_cached_and_provider_called_once(session, monkeypatch):
    currency.clear_cache()
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        return httpx.Response(200, json={"rates": {"USD": 0.012, "AED": 0.044, "EUR": 0.0110}},
                              request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    s = Settings(_env_file=None)
    usd = currency.get_inr_rate(session, "USD", s)
    assert round(usd, 2) == round(1 / 0.012, 2)
    for _ in range(50):
        currency.get_inr_rate(session, "USD", s)
        currency.get_inr_rate(session, "AED", s)
    assert len(calls) == 1  # one provider call, everything else cached
    assert currency.to_inr(session, 10, "INR", s) == 10
    assert session.get(ExchangeRate, "USD") is not None


def test_fx_falls_back_to_stale_then_configured_then_raises(session, monkeypatch):
    currency.clear_cache()
    monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))
    with pytest.raises(currency.FxUnavailable):
        currency.get_inr_rate(session, "GBP", Settings(_env_file=None))
    assert currency.get_inr_rate(session, "GBP", Settings(_env_file=None, fx_fallback_rates='{"GBP": 100}')) == 100
