from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crawlers import registry
from app.database.session import get_db
from app.models.product import RetailerProduct
from app.models.retailer import Retailer

router = APIRouter(prefix="/retailers", tags=["retailers"])


@router.get("")
def list_retailers(db: Session = Depends(get_db)) -> dict:
    registry.load_all()
    counts = dict(db.execute(select(RetailerProduct.retailer_id, func.count()).group_by(RetailerProduct.retailer_id)).all())
    out = []
    for r in db.scalars(select(Retailer).order_by(Retailer.name)):
        cls = registry.ADAPTERS.get(r.key)
        out.append({
            "key": r.key, "name": r.name, "domain": r.domain, "country": r.country, "currency": r.currency,
            "enabled": r.active, "status": r.status, "status_reason": r.status_reason,
            "consecutive_failures": r.consecutive_failures, "unavailable_until": r.unavailable_until,
            "last_success_at": r.last_success_at, "last_failure_at": r.last_failure_at,
            "listings": counts.get(r.id, 0), "access_policy": cls.access_policy if cls else None})
    return {"items": out}
