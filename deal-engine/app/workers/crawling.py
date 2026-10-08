from __future__ import annotations

from dataclasses import asdict

from app.config.settings import get_settings
from app.crawlers.base import ProductNotFound, RetailerBlocked, RetailerNotConfigured
from app.database.session import session_scope
from app.models.product import RetailerProduct
from app.services import metrics, pipeline
from app.utils.logging import get_logger
from app.workers.celery_app import RETRY_COUNTDOWNS, celery

log = get_logger(__name__)


@celery.task(name="app.workers.crawling.schedule_crawls")
def schedule_crawls() -> int:
    """Beat tick: enqueue due listings, highest priority first. Hot products use CRAWL_INTERVAL_MINUTES,
    the rest GENERAL_CRAWL_INTERVAL_MINUTES (see pipeline._next_crawl)."""
    s = get_settings()
    with session_scope() as session:
        ids = pipeline.due_listing_ids(session, s.crawl_batch_size)
        # push next_crawl_at forward so the same listing isn't queued twice before it runs
        from datetime import datetime, timedelta, timezone

        soon = datetime.now(timezone.utc) + timedelta(minutes=30)
        for rp_id in ids:
            rp = session.get(RetailerProduct, rp_id)
            if rp is not None:
                rp.next_crawl_at = soon
    for rp_id in ids:
        crawl_product.apply_async(args=[rp_id], queue="crawl")
    return len(ids)


@celery.task(name="app.workers.crawling.crawl_product", bind=True, max_retries=len(RETRY_COUNTDOWNS))
def crawl_product(self, rp_id: int) -> str:  # type: ignore[no-untyped-def]
    """Fetch one listing. A failure here only affects this listing."""
    with session_scope() as session:
        try:
            scraped = pipeline.fetch(session, rp_id)
        except RetailerBlocked as exc:
            pipeline.mark_failed(session, rp_id, str(exc))
            return "blocked"  # retailer is paused; do not retry or hammer
        except RetailerNotConfigured:
            return "not_configured"
        except ProductNotFound as exc:
            pipeline.mark_failed(session, rp_id, f"not found: {exc}", not_found=True)
            metrics.inc("crawls_failed")
            return "not_found"
        except Exception as exc:
            metrics.inc("crawls_failed")
            if self.request.retries >= self.max_retries:
                pipeline.mark_failed(session, rp_id, f"gave up after retries: {exc}")
                log.error("crawl failed permanently", extra={"listing_id": rp_id, "error": str(exc)})
                return "failed"
            raise self.retry(exc=exc, countdown=RETRY_COUNTDOWNS[self.request.retries]) from exc
    if scraped is None:
        return "skipped"
    from app.workers.matching import store_price

    store_price.apply_async(args=[rp_id, asdict(scraped)], queue="default")
    return "ok"
