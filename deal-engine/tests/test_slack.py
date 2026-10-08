import json
from datetime import datetime, timezone

import httpx
import pytest

from app.config.settings import Settings
from app.notifiers.base import NotifierNotConfigured
from app.notifiers.slack import SlackNotifier, build_blocks
from app.utils.currency import format_inr


def payload(**over):
    p = {
        "product_id": 1, "product_name": "Apple AirPods Pro 2 USB-C", "brand": "apple", "category": "electronics",
        "rating": 4.5, "review_count": 18421, "severity": "GOOD", "score": 88.0, "confidence": "HIGH",
        "history_quality": "HIGH", "match_confidence": 96.0,
        "best": {"retailer_key": "flipkart", "retailer_name": "Flipkart", "price": 12999.0, "url": "https://www.flipkart.com/p/1"},
        "others": [
            {"retailer_key": "amazon", "retailer_name": "Amazon India", "price": 13499.0, "url": "https://www.amazon.in/dp/B1"},
            {"retailer_key": "croma", "retailer_name": "Croma", "price": 14999.0, "url": "https://www.croma.com/p/9"}],
        "baseline": {"type": "median_90d", "price": 27999.0}, "discount": 53.6, "discount_from_max": 56.0,
        "discount_from_median": 53.6, "discount_from_average": 52.0,
        "stats": {"min": 12999.0, "max": 31999.0, "robust_max": 29999.0, "median": 27999.0, "average": 27500.0,
                  "n_observations": 210, "span_days": 90, "volatility": 0.1},
        "range_90d": [12999.0, 29999.0], "trend_30d": -45.0, "trend_90d": -50.0, "flags": [],
        "detected_at": datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc).isoformat(),
    }
    p.update(over)
    return p


def text_of(blocks):
    return json.dumps(blocks, ensure_ascii=False)


def test_blocks_contain_required_information():
    blocks, fallback = build_blocks(payload())
    t = text_of(blocks)
    for needle in ["Apple AirPods Pro 2 USB-C", "4.5/5", "18,421", "₹12,999", "₹27,999", "53.6%", "Flipkart",
                   "Amazon India", "₹13,499", "Croma", "₹14,999", "90-day range", "₹29,999", "HIGH", "96%",
                   "2026-10-08 10:00 UTC", "30-day trend", "90-day trend", "https://www.flipkart.com/p/1",
                   "https://www.amazon.in/dp/B1", "90-day median", "not MRP"]:
        assert needle in t, needle
    assert blocks[0]["type"] == "header" and "GOOD DEAL" in blocks[0]["text"]["text"]
    assert blocks[-1]["type"] == "actions" and blocks[-1]["elements"][0]["url"] == "https://www.flipkart.com/p/1"
    assert "mrp" not in t.lower().replace("not mrp", "")
    assert "₹12,999" in fallback


@pytest.mark.parametrize("sev,label", [("EXTREME", "EXTREME DEAL"), ("GREAT", "GREAT DEAL"), ("GOOD", "GOOD DEAL")])
def test_severity_labels(sev, label):
    assert label in build_blocks(payload(severity=sev))[0][0]["text"]["text"]


def test_single_retailer_and_low_confidence_warnings():
    blocks, _ = build_blocks(payload(others=[], history_quality="MEDIUM", flags=["no_cross_retailer_confirmation"]))
    t = text_of(blocks)
    assert "No other retailer confirmed" in t and "only one retailer" in t and "medium-confidence history" in t


def test_mrkdwn_injection_is_escaped():
    blocks, _ = build_blocks(payload(product_name="Evil <!channel> & <http://x|y>"))
    t = text_of(blocks)
    assert "<!channel>" not in t and "&lt;!channel&gt;" in t


def test_inr_format():
    assert format_inr(129999) == "₹1,29,999" and format_inr(999) == "₹999"


def test_webhook_post():
    sent = []

    def handler(req: httpx.Request):
        sent.append(json.loads(req.content))
        return httpx.Response(200, text="ok")

    n = SlackNotifier(Settings(_env_file=None, slack_webhook_url="https://hooks.slack.com/services/T/B/x"),
                      httpx.Client(transport=httpx.MockTransport(handler)))
    n.send_deal(payload())
    assert sent[0]["blocks"] and "text" in sent[0]


def test_bot_token_post_uses_category_channel():
    calls = []

    def handler(req: httpx.Request):
        calls.append((req.headers["authorization"], json.loads(req.content)))
        return httpx.Response(200, json={"ok": True})

    s = Settings(_env_file=None, slack_bot_token="xoxb-test", slack_channel_id="CDEFAULT",
                 slack_channel_map='{"electronics": "CELEC"}')
    SlackNotifier(s, httpx.Client(transport=httpx.MockTransport(handler))).send_deal(payload())
    assert calls[0][0] == "Bearer xoxb-test" and calls[0][1]["channel"] == "CELEC"
    SlackNotifier(s, httpx.Client(transport=httpx.MockTransport(handler))).send_deal(payload(category="fashion"))
    assert calls[1][1]["channel"] == "CDEFAULT"


def test_slack_failures_raise_and_unconfigured():
    n = SlackNotifier(Settings(_env_file=None, slack_webhook_url="https://x"),
                      httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, text="boom"))))
    with pytest.raises(RuntimeError):
        n.send_deal(payload())
    with pytest.raises(NotifierNotConfigured):
        SlackNotifier(Settings(_env_file=None)).send_deal(payload())
    bad = SlackNotifier(Settings(_env_file=None, slack_bot_token="t", slack_channel_id="C"),
                        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": False, "error": "channel_not_found"}))))
    with pytest.raises(RuntimeError, match="channel_not_found"):
        bad.send_deal(payload())


def test_imported_history_warning_only_when_used_and_no_redundant_raw_max():
    t = text_of(build_blocks(payload(uses_imported_history=False))[0])
    assert "imported" not in t and "raw max" in t  # default payload: raw max (31,999) differs from spike-filtered
    assert "imported" in text_of(build_blocks(payload(uses_imported_history=True))[0])
    flat = payload()
    flat["stats"] = {**flat["stats"], "max": 29999.0}
    assert "raw max" not in text_of(build_blocks(flat)[0])
