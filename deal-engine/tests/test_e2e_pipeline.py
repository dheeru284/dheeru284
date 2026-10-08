"""End-to-end: discovery -> crawl -> store -> match -> history -> detect -> dedupe -> Slack.

Retailer sites and Slack are local HTTP servers (the sandbox cannot reach real retailers). All code under
test - adapters, fetcher/robots, matching, pricing, history, detection, notifier - is the production code."""
from datetime import datetime, timedelta, timezone

import pytest
import yaml
from sqlalchemy import func, select

from app.config.settings import Settings
from app.crawlers import registry
from app.crawlers.base import RetailerBlocked, ScrapedProduct
from app.crawlers.public import PublicPageAdapter
from app.models.deal import AlertState, DealEvent
from app.models.notification import Notification
from app.models.price import DailyPrice, PriceObservation
from app.models.product import Product, RetailerProduct
from app.models.retailer import Retailer
from app.services import catalog, detection, metrics, notification_service, pipeline, pricing


@pytest.fixture
def world(server, session, tmp_path):
    def make(key, name):
        return type(f"{name}Adapter", (PublicPageAdapter,), {
            "key": key, "name": name, "domain": server.domain, "scheme": "http",
            "product_url_re": r"/p/(?P<id>\w+)", "search_url": None, "sitemap_max_urls": 0})

    classes = {k: make(k, n) for k, n in [("shop_a", "ShopA"), ("shop_b", "ShopB"), ("shop_c", "ShopC")]}
    registry.load_all()
    registry.ADAPTERS.update(classes)
    base = f"http://{server.domain}"
    (tmp_path / "categories.yaml").write_text("{}")
    (tmp_path / "seed_urls.yaml").write_text(yaml.safe_dump({
        "shop_a": [f"{base}/p/101"], "shop_b": [f"{base}/p/9001"]}))
    s = Settings(_env_file=None, config_dir=str(tmp_path), per_domain_min_interval_seconds=0, page_cache_ttl_seconds=0,
                 redis_url="redis://localhost:6399/0", slack_webhook_url=f"{base}/slack", crawl_interval_minutes=60)
    server.prices["/p/101"] = {"name": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones Black", "price": 20000,
                               "rating": 4.5, "reviews": 5300, "mpn": "WH1000XM5B"}
    server.prices["/p/9001"] = {"name": "Sony WH-1000XM5 Headphones (Black)", "price": 21000, "rating": 4.4, "reviews": 900}
    metrics.reset_for_tests()
    catalog.sync_retailers(session, s)
    for r in session.scalars(select(Retailer)):
        r.active = r.key in classes
    session.commit()
    return s, server, base


def crawl_all(session, s):
    for rp_id in pipeline.due_listing_ids(session, 100, datetime.now(timezone.utc) + timedelta(days=1)):
        scraped = pipeline.fetch(session, rp_id, s)
        if scraped:
            pipeline.store(session, rp_id, scraped, s)
    session.commit()


def backfill(session, days=60, per_day=3):
    now = datetime.now(timezone.utc)
    for rp in session.scalars(select(RetailerProduct)):
        base_price = 20000.0 if rp.retailer_product_id == "101" else 21000.0
        for d in range(days, 0, -1):
            for h in range(per_day):
                ts = now - timedelta(days=d, hours=h * 8)
                p = ScrapedProduct(rp.retailer_product_id, rp.product_url, rp.title or "", base_price, "INR", True)
                pricing.record_observation(session, rp, p, ts=ts, settings=Settings(_env_file=None))
    session.commit()


def test_full_pipeline_deal_dedup_and_slack(world, session):
    s, server, base = world

    # 1. discovery from curated URLs -> listings; first crawl stores products and baseline observation
    for key in ("shop_a", "shop_b"):
        stats = pipeline.discover(session, key, s)
        assert stats["new"] == 1
    session.commit()
    crawl_all(session, s)

    # 2. cross-retailer matching: both listings map to ONE canonical product with strong confidence
    assert session.scalar(select(func.count()).select_from(Product)) == 1
    listings = list(session.scalars(select(RetailerProduct)))
    assert len({rp.product_id for rp in listings}) == 1
    assert all(rp.match_confidence >= 80 for rp in listings)
    assert {rp.rating for rp in listings} == {4.5, 4.4}
    product_id = listings[0].product_id

    # 3. insufficient history right now -> no alert even though we will cut the price below
    server.prices["/p/101"]["price"] = 9500
    server.prices["/p/9001"]["price"] = 10200
    crawl_all(session, s)
    assert detection.detect_for_product(session, product_id, s) is None
    assert session.scalar(select(func.count()).select_from(DealEvent)) == 0

    # 4. build 60 days of observed history, then evaluate
    backfill(session)
    ev = detection.detect_for_product(session, product_id, s)
    session.commit()
    assert ev is not None
    assert ev.best_retailer == "ShopA" and ev.best_price == 9500
    assert ev.baseline_type.startswith("median_") and 19000 <= ev.baseline_price <= 21000
    assert 50 <= ev.discount_percentage <= 56 and ev.severity == "GOOD"
    assert ev.history_quality == "HIGH"
    assert [o["retailer_name"] for o in ev.details["others"]] == ["ShopB"]
    assert ev.details["best"]["url"] == f"{base}/p/101"
    assert ev.details["discount_from_median"] > 50

    # 5. Slack delivery (real HTTP to the local webhook receiver), idempotent
    assert notification_service.deliver(session, ev.id, s) == "sent"
    session.commit()
    assert len(server.slack) == 1
    msg = server.slack[0]
    blob = str(msg)
    assert "GOOD DEAL" in blob and "ShopA" in blob and "ShopB" in blob and f"{base}/p/101" in blob
    notification_service.deliver(session, ev.id, s)
    assert len(server.slack) == 1  # not re-sent
    assert session.scalar(select(Notification.status).where(Notification.deal_event_id == ev.id)) == "sent"

    # 6. duplicate suppression on the next crawl cycle
    assert detection.detect_for_product(session, product_id, s) is None
    assert metrics.snapshot()["duplicate_alerts_suppressed"] >= 1
    assert session.scalar(select(func.count()).select_from(DealEvent)) == 1

    # 7. material further price drop after the renotify window -> new alert
    server.prices["/p/101"]["price"] = 7000
    crawl_all(session, s)
    later = datetime.now(timezone.utc) + timedelta(hours=26)
    ev2 = detection.detect_for_product(session, product_id, s, now=later)
    assert ev2 is not None and ev2.best_price == 7000 and ev2.severity in ("GREAT", "EXTREME")
    assert ev2.details["alert_reason"] in ("price_dropped_materially", "discount_improved_materially", "severity_upgraded")

    # 8. history is append-only and stored with originals
    obs = session.scalars(select(PriceObservation).order_by(PriceObservation.timestamp)).all()
    assert len(obs) > 300 and all(o.source == "OBSERVED_HISTORY" for o in obs)
    assert {o.price for o in obs} >= {20000, 21000, 9500, 10200, 7000}
    assert session.scalar(select(func.count()).select_from(DailyPrice)) >= 120

    # 9. out of stock is never alerted
    server.prices["/p/101"]["in_stock"] = False
    server.prices["/p/9001"]["in_stock"] = False
    crawl_all(session, s)
    assert detection.detect_for_product(session, product_id, s, now=later + timedelta(days=2)) is None


def test_low_rating_never_alerts(world, session):
    s, server, base = world
    server.prices["/p/101"].update(rating=3.8)
    server.prices["/p/9001"].update(rating=3.7)
    for key in ("shop_a", "shop_b"):
        pipeline.discover(session, key, s)
    crawl_all(session, s)
    backfill(session)
    pid = session.scalar(select(RetailerProduct.product_id))
    server.prices["/p/101"]["price"] = 5000
    crawl_all(session, s)
    assert detection.detect_for_product(session, pid, s) is None


def test_estimated_history_is_ignored_and_imported_flagged(world, session):
    s, server, base = world
    pipeline.discover(session, "shop_a", s)
    crawl_all(session, s)
    rp = session.scalar(select(RetailerProduct))
    now = datetime.now(timezone.utc)
    for d in range(1, 61):
        pricing.record_observation(session, rp, ScrapedProduct("101", rp.product_url, "t", 20000.0), ts=now - timedelta(days=d),
                                   settings=s, source="ESTIMATED_HISTORY")
    session.commit()
    from app.services.deal_detector import build_inputs
    pts = build_inputs(session, rp.product_id, s).points
    assert len(pts) == 1  # only today's observed crawl; the 60 ESTIMATED days never feed deal detection


def test_robots_blocked_and_403_retailer_is_paused_others_continue(world, session):
    s, server, base = world
    pipeline.discover(session, "shop_a", s)
    pipeline.discover(session, "shop_b", s)
    session.commit()
    a = session.scalar(select(Retailer).where(Retailer.key == "shop_a"))
    b = session.scalar(select(Retailer).where(Retailer.key == "shop_b"))
    rp_a = session.scalar(select(RetailerProduct).where(RetailerProduct.retailer_id == a.id))

    # robots.txt disallow path
    rp_a.product_url = f"{base}/private/x"
    with pytest.raises(RetailerBlocked, match="robots"):
        pipeline.fetch(session, rp_a.id, s)
    assert a.status == "unavailable" and a.unavailable_until is not None
    # paused retailer is skipped without any request, the other retailer keeps working
    assert pipeline.fetch(session, rp_a.id, s) is None
    rp_b = session.scalar(select(RetailerProduct).where(RetailerProduct.retailer_id == b.id))
    assert pipeline.fetch(session, rp_b.id, s).price == 21000
    assert b.status == "ok"
    assert rp_a.id not in pipeline.due_listing_ids(session, 100, datetime.now(timezone.utc))  # circuit open
    assert rp_a.id in pipeline.due_listing_ids(session, 100, datetime.now(timezone.utc) + timedelta(hours=7))  # cooldown over

    # HTTP 403 / captcha
    a.status, a.unavailable_until = "ok", None
    rp_a.product_url = f"{base}/p/101"
    server.blocked_paths.add("/p/101")
    with pytest.raises(RetailerBlocked):
        pipeline.fetch(session, rp_a.id, s)
    assert a.status == "unavailable"
    assert metrics.snapshot()["retailer_blocked"] >= 2


def test_unchanged_price_not_rerecorded_but_changes_are(world, session):
    s, server, base = world
    pipeline.discover(session, "shop_a", s)
    crawl_all(session, s)
    crawl_all(session, s)
    assert session.scalar(select(func.count()).select_from(PriceObservation)) == 1
    server.prices["/p/101"]["price"] = 19000
    crawl_all(session, s)
    assert session.scalar(select(func.count()).select_from(PriceObservation)) == 2
    assert metrics.snapshot()["prices_skipped_unchanged"] >= 1


def test_coupon_membership_emi_handling(session):
    s = Settings(_env_file=None)
    r = Retailer(key="x", name="X", domain="x.in")
    session.add(r)
    session.flush()
    rp = RetailerProduct(retailer_id=r.id, retailer_product_id="1", product_url="https://x.in/p/1", title="t")
    session.add(rp)
    session.flush()
    t0 = datetime.now(timezone.utc)
    unverified = ScrapedProduct("1", "u", "t", 1000.0, coupon_discount=200.0, membership_price=700.0, shipping_cost=50.0)
    o = pricing.record_observation(session, rp, unverified, ts=t0, settings=s)
    assert (o.price, o.coupon_discount, o.coupon_verified, o.membership_price, o.effective_price) == (1000.0, 200.0, False, 700.0, 1050.0)
    verified = ScrapedProduct("1", "u", "t", 1000.0, coupon_discount=200.0, coupon_verified=True)
    o2 = pricing.record_observation(session, rp, verified, ts=t0 + timedelta(hours=7), settings=s)
    assert o2.effective_price == 800.0 and o2.coupon_verified
    emi = ScrapedProduct("1", "u", "t", 100.0, payable=False)
    o3 = pricing.record_observation(session, rp, emi, ts=t0 + timedelta(hours=14), settings=s)
    assert o3.is_payable is False
    day_rows = session.scalars(select(DailyPrice)).all()
    assert min(r.min_price for r in day_rows) == 800.0  # EMI-only price (100) excluded from roll-up
    assert all(r.min_price != 100.0 for r in day_rows)


def test_foreign_currency_normalised(session, monkeypatch):
    from app.utils import currency
    currency.clear_cache()
    session.add(__import__("app.models.price", fromlist=["ExchangeRate"]).ExchangeRate(currency="USD", inr_per_unit=80.0,
                                                                                      fetched_at=datetime.now(timezone.utc)))
    r = Retailer(key="y", name="Y", domain="y.com", currency="USD")
    session.add(r)
    session.flush()
    rp = RetailerProduct(retailer_id=r.id, retailer_product_id="1", product_url="https://y.com/p/1")
    session.add(rp)
    session.flush()
    o = pricing.record_observation(session, rp, ScrapedProduct("1", "u", "t", 10.0, "USD"), settings=Settings(_env_file=None))
    assert (o.price, o.currency, o.price_inr, o.effective_price) == (10.0, "USD", 800.0, 800.0)


def test_slack_failure_recorded_and_retry_succeeds(world, session):
    s, server, base = world
    pipeline.discover(session, "shop_a", s)
    pipeline.discover(session, "shop_b", s)
    crawl_all(session, s)
    backfill(session)
    pid = session.scalar(select(RetailerProduct.product_id))
    server.prices["/p/101"]["price"] = 9000
    crawl_all(session, s)
    ev = detection.detect_for_product(session, pid, s)
    session.commit()
    server.slack_status = 500
    with pytest.raises(RuntimeError):
        notification_service.deliver(session, ev.id, s)
    session.commit()
    assert ev.notification_status == "failed"
    server.slack_status = 200
    assert notification_service.deliver(session, ev.id, s) == "sent"
    assert session.scalar(select(Notification.attempts).where(Notification.deal_event_id == ev.id)) == 2
