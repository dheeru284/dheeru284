from pathlib import Path

from sqlalchemy import select

from app.config.settings import Settings
from app.crawlers import registry
from app.models.product import RetailerProduct
from app.notifiers.slack import SlackNotifier, build_quick_drop
from scripts import watch


def settings(server, tmp_path):
    return Settings(_env_file=None, config_dir=str(tmp_path), per_domain_min_interval_seconds=0, page_cache_ttl_seconds=0,
                    redis_url="redis://localhost:6399/0", slack_webhook_url=f"http://{server.domain}/slack",
                    first_party_retailers="")


def test_watchlist_parsing(tmp_path):
    f = tmp_path / "w.txt"
    f.write_text("# comment\n\nhttps://a.in/p/1\n  https://b.in/p/2  \n")
    assert watch.load_watchlist(f) == ["https://a.in/p/1", "https://b.in/p/2"]
    assert watch.load_watchlist(tmp_path / "missing.txt") == []


def test_unknown_site_gets_generic_adapter_and_known_site_maps_to_retailer():
    registry.load_all()
    assert watch.adapter_key_for("https://www.croma.com/x/p/123") == "croma"
    key = watch.adapter_key_for("https://shop.example-brand.com/products/thing-1")
    assert key == "site_shop_example_brand_com" and key in registry.ADAPTERS


def test_drop_triggers_plain_slack_message_once(server, session, tmp_path):
    s = settings(server, tmp_path)
    url = f"http://{server.domain}/p/777"
    server.prices["/p/777"] = {"name": "Acme Kettle 1.5L", "price": 2000, "rating": 4.4, "reviews": 120, "brand": "Acme"}
    watch_n = watch.setup(session, s, [url])
    assert watch_n == 1
    n = SlackNotifier(s)
    r1 = watch.run_cycle(session, s, n, 5)
    assert r1["checked"] == 1 and r1["drops"] == 0 and not server.slack     # first look: nothing to compare with
    server.prices["/p/777"]["price"] = 1500
    r2 = watch.run_cycle(session, s, n, 5)
    assert r2["drops"] == 1 and len(server.slack) == 1
    text = str(server.slack[0])
    assert "Acme Kettle" in text and "2,000" in text and "1,500" in text and "25% cheaper" in text and url in text
    r3 = watch.run_cycle(session, s, n, 5)                                   # unchanged: no repeat message
    assert r3["drops"] == 0 and len(server.slack) == 1
    server.prices["/p/777"]["price"] = 1450                                  # 3% drop < threshold
    assert watch.run_cycle(session, s, n, 5)["drops"] == 0


def test_blocked_site_is_reported_not_retried(server, session, tmp_path):
    s = settings(server, tmp_path)
    server.prices["/p/888"] = {"name": "Thing Two", "price": 10}
    watch.setup(session, s, [f"http://{server.domain}/p/888"])
    server.blocked_paths.add("/p/888")
    r = watch.run_cycle(session, s, SlackNotifier(s), 5)
    assert r["problems"] == 1 and r["checked"] == 0


def test_quick_drop_message_is_plain_english():
    blocks, text = build_quick_drop({"title": "Acme Kettle", "url": "https://x/p/1", "retailer_name": "Croma",
                                     "old_price": 2000.0, "new_price": 1500.0, "rating": 4.4, "review_count": 120,
                                     "history_days": 3})
    flat = str(blocks)
    for w in ("Price drop: 25% cheaper", "from ₹2,000 to *₹1,500*", "you save about ₹500", "4.4★ from 120 reviews", "Buy at Croma"):
        assert w in flat, w
    assert "→" in text and "https://x/p/1" in text
