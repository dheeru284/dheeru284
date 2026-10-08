"""Pipeline steps as plain functions (the Celery tasks are thin wrappers around these)."""
from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.crawlers import registry
from app.crawlers.base import (
    ProductCandidate,
    RetailerBlocked,
    RetailerNotConfigured,
    ScrapedProduct,
)
from app.crawlers.public import PublicPageAdapter
from app.models.product import RetailerProduct
from app.models.retailer import Retailer
from app.services import catalog, metrics, pricing, retailer_health
from app.utils.logging import get_logger

log = get_logger(__name__)


def load_categories(settings: Settings) -> dict[str, list[str]]:
    path = Path(settings.config_dir) / "categories.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return {str(k): [str(x) for x in (v or [])] for k, v in data.items()}


def load_seed_urls(settings: Settings) -> dict[str, list[str]]:
    path = Path(settings.config_dir) / "seed_urls.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return {str(k): [str(u) for u in (v or [])] for k, v in data.items()}


def _next_crawl(rp: RetailerProduct, s: Settings, now: datetime, failed: bool = False) -> datetime:
    minutes = s.crawl_interval_minutes if rp.hot else s.general_crawl_interval_minutes
    if failed:
        minutes = max(60, min(minutes, 6 * 60))
    return now + timedelta(minutes=minutes * random.uniform(0.9, 1.1))  # jitter avoids thundering herds


def discover(session: Session, retailer_key: str, settings: Settings | None = None,
             rotation: int = 0) -> dict[str, int]:
    """Discover listings for one retailer: seed URLs, category searches, sitemaps/feeds.
    Returns counts. Blocks/failures are recorded on the retailer, never raised past this function."""
    s = settings or get_settings()
    retailer = retailer_health.get_retailer(session, retailer_key)
    stats = {"found": 0, "new": 0, "stored": 0}
    if retailer is None or not retailer_health.is_available(retailer):
        return stats
    adapter = registry.get_adapter(retailer_key, s)
    cats = load_categories(s)
    # rotate through the keyword list across runs so the whole catalogue is covered over time
    flat = [(c, kw) for c, kws in cats.items() for kw in kws]
    if flat:
        start = (rotation * s.discovery_queries_per_run) % len(flat)
        window = (flat[start:] + flat[:start])[: s.discovery_queries_per_run]
        queries: dict[str, list[str]] = {}
        for c, kw in window:
            queries.setdefault(c, []).append(kw)
    else:
        queries = {}
    found: list[tuple[str | None, ProductCandidate]] = []
    try:
        for url in load_seed_urls(s).get(retailer_key, []):
            pid_fn = getattr(adapter, "candidate_from_url", None)
            cand = pid_fn(url) if pid_fn else None
            if cand:
                found.append((None, cand))
        found.extend(adapter.discover_products(queries, s.discovery_results_per_query, s.discovery_queries_per_run))
        if isinstance(adapter, PublicPageAdapter) and adapter.sitemap_max_urls:
            try:
                found.extend((None, c) for c in adapter.discover_from_sitemaps(adapter.sitemap_max_urls))
            except RetailerBlocked as exc:
                log.info("sitemap discovery not permitted", extra={"retailer": retailer_key, "reason": str(exc)})
        retailer_health.record_success(session, retailer)
    except RetailerBlocked as exc:
        retailer_health.record_failure(session, retailer, str(exc), blocked=True, settings=s)
    except RetailerNotConfigured as exc:
        retailer.status, retailer.status_reason = "unconfigured", str(exc)
    except Exception as exc:
        retailer_health.record_failure(session, retailer, f"discovery error: {exc}", settings=s)
        log.exception("discovery failed", extra={"retailer": retailer_key})
    for category, cand in found:
        stats["found"] += 1
        rp, created = catalog.upsert_listing(session, retailer, cand, category)
        if created:
            stats["new"] += 1
            rp.next_crawl_at = datetime.now(timezone.utc)
        if cand.prefetched is not None:
            store(session, rp.id, cand.prefetched, s)
            stats["stored"] += 1
    session.flush()
    log.info("discovery finished", extra={"retailer": retailer_key, **stats})
    return stats


def fetch(session: Session, rp_id: int, settings: Settings | None = None) -> ScrapedProduct | None:
    """Fetch one listing. Returns None if skipped (retailer paused). Raises adapter errors."""
    s = settings or get_settings()
    rp = session.get(RetailerProduct, rp_id)
    if rp is None or not rp.active:
        return None
    retailer = session.get(Retailer, rp.retailer_id)
    assert retailer is not None
    if not retailer_health.is_available(retailer):
        return None
    adapter = registry.get_adapter(retailer.key, s)
    started = time.monotonic()
    metrics.inc("products_scanned", retailer=retailer.key)
    try:
        scraped = adapter.fetch_listing(rp.retailer_product_id, rp.product_url)
    except RetailerBlocked as exc:
        retailer_health.record_failure(session, retailer, str(exc), blocked=True, settings=s)
        _log_crawl(retailer.key, rp, "blocked", started, error=str(exc))
        metrics.inc("crawls_failed", retailer=retailer.key)
        raise
    except Exception as exc:
        _log_crawl(retailer.key, rp, "error", started, error=str(exc))
        raise
    _log_crawl(retailer.key, rp, "ok", started, scraped=scraped)
    retailer_health.record_success(session, retailer)
    metrics.inc("crawls_succeeded", retailer=retailer.key)
    return scraped


def _log_crawl(retailer: str, rp: RetailerProduct, status: str, started: float,
               scraped: ScrapedProduct | None = None, error: str | None = None) -> None:
    log.info("crawl", extra={
        "retailer": retailer, "url": rp.product_url, "product_id": rp.product_id, "listing_id": rp.id,
        "status": status, "duration_ms": int((time.monotonic() - started) * 1000),
        "price": scraped.price if scraped else None, "rating": scraped.rating if scraped else None,
        "error": error,
    })


def store(session: Session, rp_id: int, scraped: ScrapedProduct, settings: Settings | None = None) -> int | None:
    """Persist listing attributes + a price observation + canonical product assignment."""
    s = settings or get_settings()
    rp = session.get(RetailerProduct, rp_id)
    if rp is None:
        return None
    now = datetime.now(timezone.utc)
    catalog.apply_scrape(rp, scraped)
    rp.last_crawled_at, rp.consecutive_failures, rp.last_error = now, 0, None
    catalog.assign_product(session, rp, s)
    pricing.record_observation(session, rp, scraped, ts=now, settings=s)
    rp.next_crawl_at = _next_crawl(rp, s, now)
    session.flush()
    return rp.product_id


def mark_failed(session: Session, rp_id: int, error: str, settings: Settings | None = None,
                not_found: bool = False) -> None:
    s = settings or get_settings()
    rp = session.get(RetailerProduct, rp_id)
    if rp is None:
        return
    rp.consecutive_failures += 1
    rp.last_error = error[:500]
    now = datetime.now(timezone.utc)
    rp.next_crawl_at = _next_crawl(rp, s, now, failed=True)
    if not_found and rp.consecutive_failures >= 3:
        rp.active = False  # delisted
    session.flush()


def due_listing_ids(session: Session, limit: int, now: datetime | None = None) -> list[int]:
    now = now or datetime.now(timezone.utc)
    session.flush()  # sessions run with autoflush off: make pending health/priority changes visible
    q = (
        select(RetailerProduct.id)
        .join(Retailer, Retailer.id == RetailerProduct.retailer_id)
        .where(RetailerProduct.active.is_(True), Retailer.active.is_(True),
               Retailer.status.notin_(["unconfigured"]),
               or_(Retailer.unavailable_until.is_(None), Retailer.unavailable_until <= now),
               or_(RetailerProduct.next_crawl_at.is_(None), RetailerProduct.next_crawl_at <= now))
        .order_by(RetailerProduct.priority.desc(), RetailerProduct.next_crawl_at.asc())
        .limit(limit)
    )
    return list(session.scalars(q))
