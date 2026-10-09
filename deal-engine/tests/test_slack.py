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


def test_blocks_are_plain_english_and_complete():
    blocks, fallback = build_blocks(payload())
    t = text_of(blocks)
    for needle in ["Apple AirPods Pro 2 USB-C", "4.5★ from 18,421 reviews", "Now *₹12,999* at *Flipkart*",
                   "Usually ₹27,999 over the last 90 days", "you save about *₹15,000* (54%)",
                   "Where to buy (cheapest first)", "1. <https://www.flipkart.com/p/1|Flipkart> — ₹12,999  ← cheapest",
                   "2. <https://www.amazon.in/dp/B1|Amazon India> — ₹13,499", "3. <https://www.croma.com/p/9|Croma> — ₹14,999",
                   "lowest ₹12,999, highest ₹29,999", "210 price checks over 90 days", "How sure are we: high",
                   "not the printed MRP", "Checked 08 Oct 2026, 10:00 UTC"]:
        assert needle in t, needle
    assert blocks[0]["type"] == "header" and "54% cheaper than usual" in blocks[0]["text"]["text"]
    assert blocks[-1]["type"] == "actions" and blocks[-1]["elements"][0]["url"] == "https://www.flipkart.com/p/1"
    for jargon in ("median_", "spike-filtered", "vs max", "Historical:", "discount_from"):
        assert jargon not in t
    assert fallback.startswith("Price drop: Apple AirPods Pro 2 USB-C is now ₹12,999 at Flipkart (54% cheaper than usual)")


def test_severity_titles():
    assert "Huge price drop" in build_blocks(payload(severity="EXTREME"))[0][0]["text"]["text"]
    assert "Big price drop" in build_blocks(payload(severity="GREAT"))[0][0]["text"]["text"]
    assert "Price drop:" in build_blocks(payload(severity="GOOD"))[0][0]["text"]["text"]


def test_single_store_and_short_history_warnings_in_words():
    blocks, _ = build_blocks(payload(others=[], history_quality="MEDIUM", flags=["no_cross_retailer_confirmation"]))
    t = text_of(blocks)
    assert "Only one store checked so far" in t and "Only one store confirms this price" in t and "Short price history" in t


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


def test_imported_history_note_only_when_used():
    assert "imported" not in text_of(build_blocks(payload(uses_imported_history=False))[0])
    assert "imported" in text_of(build_blocks(payload(uses_imported_history=True))[0])
