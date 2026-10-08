from __future__ import annotations

from app.crawlers.base import ScrapedProduct
from app.database.session import session_scope
from app.services import detection, pipeline
from app.workers.celery_app import celery


@celery.task(name="app.workers.matching.store_price")
def store_price(rp_id: int, scraped: dict) -> int | None:
    """Persist observation + (idempotently) assign the canonical product, then trigger detection."""
    with session_scope() as session:
        product_id = pipeline.store(session, rp_id, ScrapedProduct(**scraped))
    if product_id is not None:
        detect_deals.apply_async(args=[product_id], queue="default")
    return product_id


@celery.task(name="app.workers.matching.match_products")
def match_products(rp_id: int) -> int | None:
    """Re-run canonical matching for one listing (also used after matching rules change)."""
    from app.models.product import RetailerProduct
    from app.services import catalog

    with session_scope() as session:
        rp = session.get(RetailerProduct, rp_id)
        if rp is None:
            return None
        rp.match_notes = {**(rp.match_notes or {}), "title_hash": None}
        prod = catalog.assign_product(session, rp)
        return prod.id if prod else None


@celery.task(name="app.workers.matching.detect_deals")
def detect_deals(product_id: int) -> int | None:
    with session_scope() as session:
        event = detection.detect_for_product(session, product_id)
        event_id = event.id if event else None
        session.commit()
    if event_id:
        from app.workers.alerts import send_slack_alert

        send_slack_alert.apply_async(args=[event_id], queue="alerts")
    return event_id
