from __future__ import annotations

import time

from app.database.session import session_scope
from app.services import catalog, pipeline, retailer_health
from app.workers.celery_app import celery


@celery.task(name="app.workers.discovery.discover_products", bind=True, max_retries=0)
def discover_products(self, retailer_key: str, rotation: int = 0) -> dict:  # type: ignore[no-untyped-def]
    """Discover listings on one retailer. Never raises for retailer problems (they pause the retailer)."""
    with session_scope() as session:
        stats = pipeline.discover(session, retailer_key, rotation=rotation)
        # queue first crawls for the new listings
        from app.workers.crawling import crawl_product

        for rp_id in pipeline.due_listing_ids(session, 200):
            crawl_product.apply_async(args=[rp_id], queue="crawl")
    return stats


@celery.task(name="app.workers.discovery.discover_all")
def discover_all() -> list[str]:
    rotation = int(time.time() // 86400)
    queued = []
    with session_scope() as session:
        catalog.sync_retailers(session)
        from sqlalchemy import select

        from app.models.retailer import Retailer

        for r in session.scalars(select(Retailer).where(Retailer.active.is_(True))):
            if retailer_health.is_available(r):
                queued.append(r.key)
    for key in queued:
        discover_products.apply_async(args=[key, rotation], queue="discovery")
    return queued
