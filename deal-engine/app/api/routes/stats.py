from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.deal import DealEvent
from app.models.notification import Notification
from app.models.price import PriceObservation
from app.models.product import Product, RetailerProduct
from app.services import metrics

router = APIRouter(prefix="/stats", tags=["ops"])


@router.get("")
def stats(db: Session = Depends(get_db)) -> dict:
    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    return {
        "products": db.scalar(select(func.count()).select_from(Product)),
        "listings": db.scalar(select(func.count()).select_from(RetailerProduct)),
        "observations": db.scalar(select(func.count()).select_from(PriceObservation)),
        "observations_last_24h": db.scalar(select(func.count()).select_from(PriceObservation)
                                           .where(PriceObservation.timestamp >= day_ago)),
        "deals_total": db.scalar(select(func.count()).select_from(DealEvent)),
        "deals_last_24h": db.scalar(select(func.count()).select_from(DealEvent).where(DealEvent.detected_at >= day_ago)),
        "notifications_sent": db.scalar(select(func.count()).select_from(Notification).where(Notification.status == "sent")),
        "notifications_failed": db.scalar(select(func.count()).select_from(Notification).where(Notification.status == "failed")),
        "counters": metrics.snapshot(),
    }
