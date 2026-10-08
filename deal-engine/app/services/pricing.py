"""Recording price observations (append-only) and the daily roll-up."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.crawlers.base import ScrapedProduct
from app.models.price import OBSERVED, DailyPrice, PriceObservation
from app.models.product import RetailerProduct
from app.services import metrics
from app.utils.currency import FxUnavailable, get_inr_rate


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def bump_daily(session: Session, rp_id: int, ts: datetime, price: float, source: str) -> None:
    day = _aware(ts).astimezone(timezone.utc).date()
    for _ in range(2):
        row = session.scalar(select(DailyPrice).where(
            DailyPrice.retailer_product_id == rp_id, DailyPrice.day == day, DailyPrice.source == source))
        if row is None:
            try:
                with session.begin_nested():
                    session.add(DailyPrice(retailer_product_id=rp_id, day=day, source=source, min_price=price,
                                           max_price=price, last_price=price, obs_count=1))
                return
            except IntegrityError:
                continue  # concurrent insert: re-read and update
        row.min_price, row.max_price = min(row.min_price, price), max(row.max_price, price)
        row.last_price, row.obs_count = price, row.obs_count + 1
        return


def record_observation(session: Session, rp: RetailerProduct, p: ScrapedProduct, *, ts: datetime | None = None,
                       settings: Settings | None = None, source: str = OBSERVED) -> PriceObservation | None:
    """Store one observation. Returns None when nothing was stored (unchanged within heartbeat window,
    or unusable price). Observations are never updated or deleted by this path."""
    s = settings or get_settings()
    ts = ts or datetime.now(timezone.utc)
    if p.price is None or p.price <= 0:
        return None
    try:
        rate = get_inr_rate(session, p.currency, s)
    except FxUnavailable:
        return None  # cannot normalise to INR -> do not record a wrong number
    price_inr = round(p.price * rate, 2)
    shipping = round((p.shipping_cost or 0.0) * rate, 2)
    coupon = round(p.coupon_discount * rate, 2) if p.coupon_discount else None
    membership = round(p.membership_price * rate, 2) if p.membership_price else None
    mrp = round(p.mrp * rate, 2) if p.mrp else None
    # Coupons only reduce the effective price when verified as automatically applicable.
    effective = round(price_inr + shipping - (coupon if (coupon and p.coupon_verified) else 0.0), 2)
    payable = bool(p.payable) and (p.condition in (None, "new"))

    last = session.scalar(select(PriceObservation).where(PriceObservation.retailer_product_id == rp.id,
                                                       PriceObservation.timestamp <= ts)
                          .order_by(PriceObservation.timestamp.desc()).limit(1))
    if last is not None and source == OBSERVED:
        same = (abs(last.effective_price - effective) < 0.005 and last.availability == p.in_stock
                and last.is_payable == payable)
        if same and _aware(ts) - _aware(last.timestamp) < timedelta(hours=s.heartbeat_hours):
            metrics.inc("prices_skipped_unchanged")
            return None

    obs = PriceObservation(
        retailer_product_id=rp.id, timestamp=ts, price=p.price, currency=p.currency.upper(), price_inr=price_inr,
        shipping_cost=shipping, coupon_discount=coupon, coupon_verified=bool(p.coupon_verified and coupon),
        membership_price=membership, mrp_inr=mrp, effective_price=effective, availability=bool(p.in_stock),
        is_payable=payable, seller=p.seller, source=source,
    )
    session.add(obs)
    if p.in_stock and payable:
        bump_daily(session, rp.id, ts, effective, source)
    rp.mrp_inr = mrp
    session.flush()
    metrics.inc("prices_recorded")
    return obs
