from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.deal import DealEvent
from app.models.product import Product

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("")
def list_deals(
    retailer: str | None = None, category: str | None = None, min_discount: float | None = None,
    min_rating: float | None = None, min_price: float | None = None, max_price: float | None = None,
    since: datetime | None = None, confidence: str | None = Query(None, pattern="^(?i)(low|medium|high)$"),
    severity: str | None = Query(None, pattern="^(?i)(good|great|extreme)$"), notification_status: str | None = None,
    limit: int = Query(50, le=500), offset: int = 0, db: Session = Depends(get_db),
) -> dict:
    stmt = select(DealEvent, Product).join(Product, Product.id == DealEvent.product_id)
    if category:
        stmt = stmt.where(Product.category == category)
    if min_discount is not None:
        stmt = stmt.where(DealEvent.discount_percentage >= min_discount)
    if min_price is not None:
        stmt = stmt.where(DealEvent.best_price >= min_price)
    if max_price is not None:
        stmt = stmt.where(DealEvent.best_price <= max_price)
    if since:
        stmt = stmt.where(DealEvent.detected_at >= since)
    if confidence:
        stmt = stmt.where(DealEvent.confidence == confidence.upper())
    if severity:
        stmt = stmt.where(DealEvent.severity == severity.upper())
    if notification_status:
        stmt = stmt.where(DealEvent.notification_status == notification_status)
    rows = db.execute(stmt.order_by(DealEvent.detected_at.desc()).limit(limit * 3 if (retailer or min_rating) else limit)
                      .offset(offset)).all()
    items = []
    for ev, prod in rows:
        d = ev.details or {}
        if retailer and retailer not in {d.get("best", {}).get("retailer_key"), *[o["retailer_key"] for o in d.get("others", [])]}:
            continue
        if min_rating is not None and (d.get("rating") or 0) < min_rating:
            continue
        items.append({
            "id": ev.id, "product_id": prod.id, "product": prod.canonical_name, "brand": prod.brand,
            "category": prod.category, "detected_at": ev.detected_at, "current_price": ev.current_price,
            "baseline_price": ev.baseline_price, "baseline_type": ev.baseline_type,
            "discount_percentage": round(ev.discount_percentage, 2), "best_retailer": ev.best_retailer,
            "best_price": ev.best_price, "best_url": d.get("best", {}).get("url"), "deal_score": ev.deal_score,
            "confidence": ev.confidence, "severity": ev.severity, "history_quality": ev.history_quality,
            "rating": d.get("rating"), "review_count": d.get("review_count"),
            "notification_status": ev.notification_status,
        })
    return {"items": items[:limit]}
