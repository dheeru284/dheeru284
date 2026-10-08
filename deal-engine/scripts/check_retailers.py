"""Probe every registered retailer the way the crawler would, and print what works.
Run from a machine with open internet access:  python -m scripts.check_retailers [--json] [key ...]

Per retailer it reports: configuration (API keys / feed), robots.txt verdict for the search URL, and for each
URL in config/seed_urls.yaml whether it is allowed, blocked, or parsed into price/rating data.
It makes at most one robots.txt request plus one request per probed URL, throttled, and never retries
or alters headers after a refusal."""
import json
import sys
from urllib.parse import quote_plus

from app.config.settings import get_settings
from app.crawlers import registry
from app.crawlers.base import ParseError, RetailerBlocked, RetailerError, RetailerNotConfigured
from app.crawlers.public import PublicPageAdapter
from app.services.pipeline import load_seed_urls


def probe(key: str, settings) -> dict:  # type: ignore[no-untyped-def]
    ad = registry.get_adapter(key, settings)
    res: dict = {"retailer": key, "enabled": registry.is_enabled(key, settings), "source": type(ad).__name__,
                 "configured": ad.is_configured(), "search": "n/a", "pages": []}
    if not ad.is_configured():
        res["verdict"] = f"UNCONFIGURED: add API credentials or FEED_{key.upper()}_URL"
        return res
    if isinstance(ad, PublicPageAdapter) and ad.search_url:
        url = ad.search_url.format(query=quote_plus("test"))
        try:
            ad.fetcher.check_allowed(url)
            res["search"] = "allowed by robots.txt"
        except RetailerBlocked as exc:
            res["search"] = f"NOT permitted or robots.txt unreachable ({exc})"
    seeds = load_seed_urls(settings).get(key, [])
    for url in seeds:
        entry: dict = {"url": url}
        try:
            p = ad.fetch_product(url)
            entry.update(status="OK", title=p.title[:60], price=p.price, currency=p.currency, rating=p.rating,
                         reviews=p.review_count, in_stock=p.in_stock, gtin=p.gtin, mpn=p.mpn)
        except RetailerBlocked as exc:
            entry.update(status="BLOCKED", detail=str(exc))
        except ParseError as exc:
            entry.update(status="NO_STRUCTURED_DATA", detail=str(exc))
        except RetailerNotConfigured as exc:
            entry.update(status="UNCONFIGURED", detail=str(exc))
        except RetailerError as exc:
            entry.update(status="ERROR", detail=str(exc))
        res["pages"].append(entry)
    statuses = {p["status"] for p in res["pages"]}
    if not seeds:
        res["verdict"] = "UNTESTED: add sample product URLs for this retailer to config/seed_urls.yaml"
    elif statuses == {"OK"}:
        res["verdict"] = "WORKS"
    elif "OK" in statuses:
        res["verdict"] = "PARTIAL"
    elif "BLOCKED" in statuses:
        res["verdict"] = "BLOCKED: use the official API or an affiliate feed"
    else:
        res["verdict"] = "FAILING: " + ", ".join(sorted(statuses))
    return res


def _post_slack(results: list[dict]) -> None:
    """Post the probe table to Slack (same webhook/bot-token config as deal alerts)."""
    import httpx

    s = get_settings()
    ok = [r for r in results if r["verdict"] in ("WORKS", "PARTIAL")]
    lines = [f"*Retailer probe:* {len(ok)}/{len(results)} usable"]
    for r in results:
        icon = "✅" if r["verdict"] == "WORKS" else "🟡" if r["verdict"] == "PARTIAL" else "⚪" if r["verdict"].startswith(("UNTESTED", "UNCONFIGURED")) else "⛔"
        lines.append(f"{icon} `{r['retailer']}` — {r['verdict']}")
        for p in r["pages"]:
            if p["status"] == "OK":
                lines.append(f"      <{p['url']}|{p['title']}> — {p['currency']} {p['price']}")
    text = "\n".join(lines)
    if s.slack_bot_token and s.slack_channel_id:
        r = httpx.post("https://slack.com/api/chat.postMessage", headers={"Authorization": f"Bearer {s.slack_bot_token}"},
                       json={"channel": s.slack_channel_id, "text": text}, timeout=15)
        r.raise_for_status()
    elif s.slack_webhook_url:
        httpx.post(s.slack_webhook_url, json={"text": text}, timeout=15).raise_for_status()
    else:
        print("Slack not configured; skipping --slack", file=sys.stderr)


def main(argv: list[str]) -> int:
    s = get_settings()
    registry.load_all(s)
    as_json = "--json" in argv
    keys = [a for a in argv if not a.startswith("--")] or list(registry.ADAPTERS)
    results = [probe(k, s) for k in keys]
    if "--slack" in argv:
        _post_slack(results)
    if as_json:
        print(json.dumps(results, indent=2, default=str))
    else:
        print(f"{'RETAILER':18} {'SOURCE':18} {'SEARCH':28} VERDICT")
        for r in results:
            print(f"{r['retailer']:18} {r['source']:18} {r['search'][:27]:28} {r['verdict']}")
            for p in r["pages"]:
                extra = (f"{p['currency']} {p['price']} rating={p['rating']} reviews={p['reviews']}"
                         if p["status"] == "OK" else p.get("detail", ""))
                print(f"    {p['status']:18} {p['url'][:70]}  {extra}")
    return 0 if all(r["verdict"] in ("WORKS", "PARTIAL") or r["verdict"].startswith(("UNCONFIGURED", "UNTESTED")) for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
