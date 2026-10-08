"""Orchestrates detect -> de-duplicate -> persist DealEvent."""
from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.models.deal import AlertState, DealEvent
from app.models.product import RetailerProduct
from app.services import metrics
from app.services.deal_detector import DealDecision, build_inputs, decide
from app.services.dedup import AlertSnapshot, should_notify
from app.services.notification_service import build_payload
from app.utils.logging import get_logger

log = get_logger(__name__)


def update_priorities(session: Session, product_id: int, d: DealDecision, active_alert: bool) -> None:
    hot = d.near_miss or active_alert
    for rp in session.scalars(select(RetailerProduct).where(RetailerProduct.product_id == product_id)):
        base = int((rp.rating or 0) * 10 + math.log10((rp.review_count or 0) + 1) * 10)
        rp.hot, rp.priority = hot, base + (50 if hot else 0)


def detect_for_product(session: Session, product_id: int, settings: Settings | None = None,
                       now: datetime | None = None) -> DealEvent | None:
    s = settings or get_settings()
    now = now or datetime.now(timezone.utc)
    inp = build_inputs(session, product_id, s, now)
    if inp is None:
        return None
    d = decide(inp, s)
    state = session.get(AlertState, product_id)
    if state is None:
        state = AlertState(product_id=product_id, active=False, miss_count=0)
        session.add(state)

    event: DealEvent | None = None
    if d.qualifies and d.best and d.discount is not None:
        metrics.inc("deals_detected")
        snap = AlertSnapshot(state.active, state.last_alert_at, state.last_alert_price, state.last_alert_discount,
                             state.last_alert_severity, state.last_alert_retailer, state.miss_count)
        notify, why = should_notify(snap, d.best.price, d.discount, d.severity, d.best.retailer_key, now, s)
        state.miss_count = 0
        if notify:
            payload = build_payload(inp, d, s)
            payload["alert_reason"] = why
            event = DealEvent(
                product_id=product_id, detected_at=now, current_price=d.best.price, baseline_price=d.baseline_price,  # type: ignore[arg-type]
                discount_percentage=d.discount, baseline_type=d.baseline_type,  # type: ignore[arg-type]
                best_retailer=d.best.retailer_name, best_price=d.best.price, deal_score=d.score,
                confidence=d.confidence, severity=d.severity or "GOOD", history_quality=d.history_quality,
                notification_status="pending", details=payload,
            )
            session.add(event)
            state.active, state.last_alert_at = True, now
            state.last_alert_price, state.last_alert_discount = d.best.price, d.discount
            state.last_alert_severity, state.last_alert_retailer = d.severity, d.best.retailer_key
            log.info("deal detected", extra={"product_id": product_id, "discount": round(d.discount, 1),
                                             "price": d.best.price, "reason": why})
        else:
            metrics.inc("duplicate_alerts_suppressed")
            log.info("duplicate alert suppressed", extra={"product_id": product_id, "reason": why})
    else:
        if state.active:
            state.miss_count += 1
            if state.miss_count >= s.deal_miss_tolerance:
                state.active = False  # deal is gone; a later re-appearance will alert again
    update_priorities(session, product_id, d, state.active)
    session.flush()
    return event
