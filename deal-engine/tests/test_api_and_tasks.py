from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.config.settings import Settings
from app.crawlers.base import ScrapedProduct
from app.database.session import get_db
from app.models.deal import DealEvent
from app.models.product import RetailerProduct
from app.models.retailer import Retailer
from app.services import catalog, detection, pipeline, pricing
from tests.test_e2e_pipeline import backfill, crawl_all, world  # noqa: F401  (fixtures)


@pytest.fixture
def client(engine, session, monkeypatch):
    from app.api.main import app

    Session = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    def override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.setenv("FIRST_PARTY_RETAILERS", "shop_a,shop_b,shop_c")
    from app.config import settings as _s
    _s.get_settings.cache_clear()
    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
    _s.get_settings.cache_clear()


def build_deal(world, session):  # noqa: F811
    s, server, base = world
    for k in ("shop_a", "shop_b"):
        pipeline.discover(session, k, s)
    crawl_all(session, s)
    backfill(session)
    pid = session.scalar(select(RetailerProduct.product_id))
    server.prices["/p/101"]["price"] = 9500
    server.prices["/p/9001"]["price"] = 10200
    crawl_all(session, s)
    ev = detection.detect_for_product(session, pid, s)
    session.commit()
    return pid, ev


def test_api_endpoints(world, session, client):  # noqa: F811
    pid, ev = build_deal(world, session)
    assert client.get("/health").json()["database"] == "ok"
    assert "dealengine_prices_recorded_total" in client.get("/metrics").text

    r = client.get("/products", params={"retailer": "shop_a", "min_rating": 4.0}).json()
    assert r["total"] == 1 and r["items"][0]["best_price"] == 9500
    assert client.get("/products", params={"min_rating": 4.9}).json()["total"] == 0
    assert client.get("/products", params={"max_price": 100}).json()["total"] == 0
    assert client.get("/products", params={"q": "wh-1000xm5"}).json()["total"] == 1

    d = client.get(f"/products/{pid}").json()
    assert d["best_price"]["best_retailer"] == "shop_a" and d["best_price"]["current_best_price"] == 9500
    comp = {c["retailer"]: c for c in d["best_price"]["comparison"]}
    assert comp["shop_b"]["price_difference_vs_best"] == 700 and round(comp["shop_b"]["price_difference_percentage"], 1) == 7.4
    assert d["history"]["quality"] == "HIGH" and d["deal"]["qualifies"] and d["history"]["medians"]["30d"] == 20000
    assert client.get("/products/99999").status_code == 404

    h = client.get(f"/products/{pid}/history", params={"days": 90}).json()
    assert h["granularity"] == "daily" and len(h["points"]) >= 100
    raw = client.get(f"/products/{pid}/history", params={"granularity": "raw", "retailer": "shop_a"}).json()
    assert raw["points"] and all(p["retailer"] == "shop_a" for p in raw["points"])

    deals = client.get("/deals", params={"min_discount": 50, "confidence": "high"}).json()["items"]
    assert len(deals) == 1 and deals[0]["best_retailer"] == "ShopA" and deals[0]["best_url"].endswith("/p/101")
    assert client.get("/deals", params={"min_discount": 90}).json()["items"] == []
    assert client.get("/deals", params={"retailer": "shop_b"}).json()["items"]
    assert client.get("/deals", params={"retailer": "nope"}).json()["items"] == []

    ret = {x["key"]: x for x in client.get("/retailers").json()["items"]}
    assert ret["shop_a"]["listings"] == 1 and ret["amazon"]["status"] == "unconfigured"
    assert client.get("/stats").json()["deals_total"] == 1


def test_celery_task_chain_eager(world, session, monkeypatch, engine):  # noqa: F811
    """crawl_product -> store_price -> detect_deals -> send_slack_alert, executed through the real task code."""
    s, server, base = world
    import app.config.settings as cfg
    from app.workers import alerts, crawling, discovery, matching
    from app.workers.celery_app import celery

    monkeypatch.setattr(cfg, "get_settings", lambda: s)
    for mod in (crawling, matching, alerts, discovery):
        if hasattr(mod, "get_settings"):
            monkeypatch.setattr(mod, "get_settings", lambda: s)
    import app.services.catalog as cat
    import app.services.pipeline as pl
    for mod in (pl, cat):
        monkeypatch.setattr(mod, "get_settings", lambda: s)
    import app.crawlers.registry as reg
    import app.services.detection as det
    import app.services.notification_service as ns
    for mod in (ns, det, reg):
        monkeypatch.setattr(mod, "get_settings", lambda: s)
    celery.conf.task_always_eager = True
    celery.conf.task_eager_propagates = True

    for k in ("shop_a", "shop_b"):
        pipeline.discover(session, k, s)
    session.commit()
    ids = [r.id for r in session.scalars(select(RetailerProduct))]
    for i in ids:
        assert crawling.crawl_product.apply(args=[i]).get() == "ok"
    backfill(session)
    server.prices["/p/101"]["price"] = 9000
    for i in ids:
        pipeline.mark_failed(session, i, "x")  # irrelevant failure bookkeeping must not break the chain
    session.commit()
    rp101 = session.scalar(select(RetailerProduct).where(RetailerProduct.retailer_product_id == "101"))
    assert crawling.crawl_product.apply(args=[rp101.id]).get() == "ok"

    session.expire_all()
    ev = session.scalar(select(DealEvent))
    assert ev is not None and ev.notification_status == "sent" and len(server.slack) == 1
    # second pass: duplicate suppressed, no second Slack message
    crawling.crawl_product.apply(args=[rp101.id]).get()
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(DealEvent)) == 1 and len(server.slack) == 1


def test_crawl_task_failure_is_isolated(world, session, monkeypatch):  # noqa: F811
    s, server, base = world
    import app.services.pipeline as pl
    from app.workers import crawling
    monkeypatch.setattr(pl, "get_settings", lambda: s)
    pipeline.discover(session, "shop_a", s)
    session.commit()
    rp = session.scalar(select(RetailerProduct))
    server.prices.pop("/p/101")  # now 404
    for _ in range(3):
        assert crawling.crawl_product.apply(args=[rp.id]).get() == "not_found"
    session.expire_all()
    assert session.get(RetailerProduct, rp.id).active is False  # delisted after repeated 404s


def test_retry_sweep_requeues_failed_recent_alerts_only(world, session, monkeypatch):  # noqa: F811
    s, server, base = world
    pid, ev = build_deal(world, session)
    from app.workers import alerts

    queued = []
    monkeypatch.setattr(alerts.send_slack_alert, "apply_async", lambda args, queue: queued.append(args[0]))
    ev.notification_status = "failed"
    session.commit()
    assert alerts.retry_pending_alerts() == 1 and queued == [ev.id]
    ev.detected_at = datetime.now(timezone.utc) - timedelta(days=3)  # stale failures are left alone
    session.commit()
    assert alerts.retry_pending_alerts() == 0
