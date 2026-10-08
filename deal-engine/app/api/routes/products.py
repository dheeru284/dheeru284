from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database.session import get_db
from app.models.price import DailyPrice, PriceObservation
from app.models.product import Product, RetailerProduct
from app.models.retailer import Retailer
from app.services.deal_detector import build_inputs, decide, rank_offers

router = APIRouter(prefix="/products", tags=["products"])


def _latest_price_subq():  # type: ignore[no-untyped-def]
    latest_ts = (select(PriceObservation.retailer_product_id.label("rp"), func.max(PriceObservation.timestamp).label("ts"))
                 .group_by(PriceObservation.retailer_product_id).subquery())
    return (select(PriceObservation.retailer_product_id.label("rp"), PriceObservation.effective_price.label("price"),
                   PriceObservation.availability.label("in_stock"))
            .join(latest_ts, (PriceObservation.retailer_product_id == latest_ts.c.rp)
                  & (PriceObservation.timestamp == latest_ts.c.ts)).subquery())


@router.get("")
def list_products(
    q: str | None = None, retailer: str | None = None, category: str | None = None, brand: str | None = None,
    min_rating: float | None = None, min_price: float | None = None, max_price: float | None = None,
    updated_since: datetime | None = None, limit: int = Query(50, le=500), offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    lp = _latest_price_subq()
    best_q = (select(RetailerProduct.product_id.label("pid"), func.min(lp.c.price).label("best_price"),
                   func.max(RetailerProduct.rating).label("rating"), func.max(RetailerProduct.review_count).label("reviews"),
                   func.count(RetailerProduct.id).label("listings"))
            .join(lp, lp.c.rp == RetailerProduct.id).join(Retailer, Retailer.id == RetailerProduct.retailer_id)
            .where(lp.c.in_stock.is_(True), RetailerProduct.product_id.is_not(None)))
    if retailer:
        best_q = best_q.where(Retailer.key == retailer)
    best = best_q.group_by(RetailerProduct.product_id).subquery()
    stmt = select(Product, best.c.best_price, best.c.rating, best.c.reviews, best.c.listings).outerjoin(
        best, best.c.pid == Product.id)
    if q:
        stmt = stmt.where(Product.canonical_name.ilike(f"%{q}%"))
    if category:
        stmt = stmt.where(Product.category == category)
    if brand:
        stmt = stmt.where(Product.brand == brand.lower())
    if retailer:
        stmt = stmt.where(best.c.pid.is_not(None))
    if min_rating is not None:
        stmt = stmt.where(best.c.rating >= min_rating)
    if min_price is not None:
        stmt = stmt.where(best.c.best_price >= min_price)
    if max_price is not None:
        stmt = stmt.where(best.c.best_price <= max_price)
    if updated_since:
        stmt = stmt.where(Product.updated_at >= updated_since)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(Product.id.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [
        {"id": p.id, "name": p.canonical_name, "brand": p.brand, "model": p.model, "category": p.category,
         "gtin": p.gtin, "best_price": bp, "rating": r, "review_count": rv, "listings": n or 0}
        for p, bp, r, rv, n in rows]}


@router.get("/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "product not found")
    now = datetime.now(timezone.utc)
    inp = build_inputs(db, product_id, s, now)
    decision = decide(inp, s) if inp else None
    ranked = rank_offers(inp.offers, s, now) if inp else []
    best = ranked[0] if ranked else None
    listings = []
    for rp, ret in db.execute(select(RetailerProduct, Retailer).join(Retailer, Retailer.id == RetailerProduct.retailer_id)
                              .where(RetailerProduct.product_id == product_id)):
        last = db.scalar(select(PriceObservation).where(PriceObservation.retailer_product_id == rp.id)
                         .order_by(PriceObservation.timestamp.desc()).limit(1))
        listings.append({
            "listing_id": rp.id, "retailer": ret.key, "title": rp.title, "url": rp.product_url, "rating": rp.rating,
            "review_count": rp.review_count, "seller": rp.seller, "variant": rp.variant,
            "match_confidence": rp.match_confidence,
            "latest": None if last is None else {
                "timestamp": last.timestamp, "price": last.price, "currency": last.currency, "price_inr": last.price_inr,
                "effective_price": last.effective_price, "coupon_discount": last.coupon_discount,
                "coupon_verified": last.coupon_verified, "membership_price": last.membership_price,
                "shipping_cost": last.shipping_cost, "in_stock": last.availability, "payable": last.is_payable,
                "mrp_informational": last.mrp_inr},
        })
    st = decision.stats if decision else None
    return {
        "id": product.id, "name": product.canonical_name, "brand": product.brand, "model": product.model,
        "category": product.category, "gtin": product.gtin, "mpn": product.manufacturer_part_number,
        "attributes": product.normalized_attributes, "rating": inp.rating if inp else None,
        "review_count": inp.review_count if inp else None, "listings": listings,
        "best_price": None if best is None else {
            "current_best_price": best.price, "best_retailer": best.retailer_key, "best_price_url": best.url,
            "comparison": [{"retailer": o.retailer_key, "price": o.price, "url": o.url,
                            "price_difference_vs_best": round(o.price - best.price, 2),
                            "price_difference_percentage": round((o.price - best.price) / best.price * 100, 2)}
                           for o in ranked]},
        "history": None if st is None else {
            "n_observations": st.n_observations, "n_days": st.n_days, "span_days": st.span_days, "quality": st.quality,
            "insufficient": st.insufficient, "min": st.min_price, "max": st.max_price, "robust_max": st.robust_max,
            "average": st.average, "median": st.median, "volatility": st.volatility,
            "averages": {f"{k}d": v for k, v in st.avg.items()},
            "medians": {("lifetime" if k == 0 else f"{k}d"): v for k, v in st.med.items()},
            "historical_best_market_price": st.min_price, "notes": st.notes},
        "deal": None if decision is None else {
            "qualifies": decision.qualifies, "reasons": decision.reasons, "baseline_price": decision.baseline_price,
            "baseline_type": decision.baseline_type, "discount_pct": decision.discount,
            "market_discount_percentage": decision.market_discount_pct,
            "discount_from_max": decision.discount_from_max, "discount_from_median": decision.discount_from_median,
            "discount_from_average": decision.discount_from_average, "score": decision.score,
            "confidence": decision.confidence, "severity": decision.severity},
    }


@router.get("/{product_id}/history")
def product_history(product_id: int, retailer: str | None = None, days: int = Query(90, le=3650),
                    granularity: str = Query("daily", pattern="^(daily|raw)$"), limit: int = Query(5000, le=50000),
                    db: Session = Depends(get_db)) -> dict:
    if db.get(Product, product_id) is None:
        raise HTTPException(404, "product not found")
    ids_q = (select(RetailerProduct.id, Retailer.key).join(Retailer, Retailer.id == RetailerProduct.retailer_id)
             .where(RetailerProduct.product_id == product_id))
    if retailer:
        ids_q = ids_q.where(Retailer.key == retailer)
    keys = {i: k for i, k in db.execute(ids_q)}
    since = datetime.now(timezone.utc) - timedelta(days=days)
    if granularity == "raw":
        obs_rows = db.scalars(select(PriceObservation).where(
            PriceObservation.retailer_product_id.in_(keys), PriceObservation.timestamp >= since)
            .order_by(PriceObservation.timestamp).limit(limit))
        return {"product_id": product_id, "granularity": "raw", "points": [
            {"retailer": keys[o.retailer_product_id], "timestamp": o.timestamp, "price": o.price, "currency": o.currency,
             "effective_price": o.effective_price, "in_stock": o.availability, "source": o.source} for o in obs_rows]}
    daily_rows = db.scalars(select(DailyPrice).where(DailyPrice.retailer_product_id.in_(keys),
                                               DailyPrice.day >= since.date()).order_by(DailyPrice.day).limit(limit))
    return {"product_id": product_id, "granularity": "daily", "points": [
        {"retailer": keys[d.retailer_product_id], "day": d.day, "min": d.min_price, "max": d.max_price,
         "last": d.last_price, "observations": d.obs_count, "source": d.source} for d in daily_rows]}
