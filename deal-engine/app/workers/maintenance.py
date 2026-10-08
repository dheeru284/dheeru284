from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.config.settings import get_settings
from app.database.session import session_scope
from app.models.price import DailyPrice, PriceObservation
from app.utils import currency
from app.utils.logging import get_logger
from app.workers.celery_app import celery

log = get_logger(__name__)


@celery.task(name="app.workers.maintenance.aggregate_history")
def aggregate_history(days_back: int = 2) -> int:
    """Rebuild the last N days of DailyPrice from raw observations (idempotent; repairs gaps)."""
    since = datetime.now(timezone.utc) - timedelta(days=days_back)
    n = 0
    with session_scope() as session:
        rows = session.execute(
            select(PriceObservation.retailer_product_id, func.date(PriceObservation.timestamp),
                   PriceObservation.source, func.min(PriceObservation.effective_price),
                   func.max(PriceObservation.effective_price), func.count())
            .where(PriceObservation.timestamp >= since, PriceObservation.availability.is_(True),
                   PriceObservation.is_payable.is_(True))
            .group_by(PriceObservation.retailer_product_id, func.date(PriceObservation.timestamp), PriceObservation.source)
        ).all()
        for rp_id, day, source, lo, hi, cnt in rows:
            if isinstance(day, str):
                day = datetime.strptime(day, "%Y-%m-%d").date()
            row = session.scalar(select(DailyPrice).where(
                DailyPrice.retailer_product_id == rp_id, DailyPrice.day == day, DailyPrice.source == source))
            if row is None:
                session.add(DailyPrice(retailer_product_id=rp_id, day=day, source=source, min_price=lo,
                                       max_price=hi, last_price=hi, obs_count=cnt))
            else:
                row.min_price, row.max_price, row.obs_count = lo, hi, cnt
            n += 1
    return n


@celery.task(name="app.workers.maintenance.cleanup")
def cleanup() -> int:
    """Drop raw observations older than RETENTION_DAYS. DailyPrice roll-ups are kept."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().retention_days)
    with session_scope() as session:
        res = session.execute(delete(PriceObservation).where(PriceObservation.timestamp < cutoff))
        return int(getattr(res, "rowcount", 0) or 0)


@celery.task(name="app.workers.maintenance.refresh_fx")
def refresh_fx() -> int:
    with session_scope() as session:
        try:
            return len(currency.refresh_rates(session))
        except Exception as exc:
            log.warning("fx refresh failed", extra={"error": str(exc)})
            return 0
