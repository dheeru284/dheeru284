"""Test each configured credential once and report working/failing. Never prints secrets.
Usage: python -m scripts.check_credentials"""
import os
import sys

import httpx

from app.config.settings import get_settings
from app.crawlers.amazon import AmazonAdapter
from app.crawlers.base import RetailerBlocked, RetailerError
from app.crawlers.feed import FeedAdapter
from app.crawlers.flipkart import FlipkartAdapter
from app.crawlers.registry import load_all


def check_slack(s) -> tuple[str, str]:  # type: ignore[no-untyped-def]
    if s.slack_bot_token:
        r = httpx.post("https://slack.com/api/auth.test", headers={"Authorization": f"Bearer {s.slack_bot_token}"}, timeout=15)
        d = r.json()
        return ("OK", "bot token valid") if d.get("ok") else ("FAIL", f"slack: {d.get('error')}")
    if s.slack_webhook_url:
        return "SET", "webhook present (use scripts.send_test_alert to verify delivery)"
    return "MISSING", "SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN+SLACK_CHANNEL_ID"


def check_amazon(s) -> tuple[str, str]:  # type: ignore[no-untyped-def]
    ad = AmazonAdapter(s)
    if not ad.is_configured():
        return "MISSING", "AMAZON_PAAPI_ACCESS_KEY / _SECRET_KEY / _PARTNER_TAG"
    try:
        ad.search_products("headphones", 1)
        return "OK", "PA-API search succeeded"
    except RetailerBlocked as e:
        return "FAIL", f"{e} (AssociateNotEligible/403 usually means the sales requirement isn't met yet)"
    except RetailerError as e:
        return "FAIL", str(e)[:150]


def check_flipkart(s) -> tuple[str, str]:  # type: ignore[no-untyped-def]
    ad = FlipkartAdapter(s)
    if not ad.is_configured():
        return "MISSING", "FLIPKART_AFFILIATE_ID / FLIPKART_AFFILIATE_TOKEN"
    try:
        n = len(ad.search_products("headphones", 1))
        return "OK", f"Affiliate API search succeeded ({n} result)"
    except RetailerError as e:
        return "FAIL", str(e)[:150]


def check_feeds(s) -> list[tuple[str, str, str]]:  # type: ignore[no-untyped-def]
    out = []
    from app.crawlers import registry

    for key, cls in registry.ADAPTERS.items():
        if os.environ.get(f"FEED_{key.upper()}_URL"):
            try:
                n = len(FeedAdapter(cls, s)._load())
                out.append((f"feed:{key}", "OK" if n else "FAIL", f"{n} products parsed"))
            except Exception as e:  # noqa: BLE001
                out.append((f"feed:{key}", "FAIL", str(e)[:150]))
    return out


def main() -> int:
    s = get_settings()
    load_all(s)
    rows = [("slack", *check_slack(s)), ("amazon", *check_amazon(s)), ("flipkart", *check_flipkart(s)), *check_feeds(s)]
    for name, status, detail in rows:
        print(f"{name:18} {status:8} {detail}")
    return 1 if any(r[1] == "FAIL" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
