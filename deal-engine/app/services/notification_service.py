from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.models.deal import DealEvent
from app.models.notification import Notification
from app.notifiers import NOTIFIERS
from app.notifiers.base import NotifierNotConfigured
from app.services import metrics
from app.services.deal_detector import DealDecision, DealInputs, OfferInfo
from app.utils.logging import get_logger

log = get_logger(__name__)


def _offer(o: OfferInfo) -> dict[str, Any]:
    return {"retailer_key": o.retailer_key, "retailer_name": o.retailer_name, "price": o.price, "url": o.url,
            "match_confidence": o.match_confidence}


def build_payload(inp: DealInputs, d: DealDecision, settings: Settings) -> dict[str, Any]:
    assert d.qualifies and d.best and d.stats and d.baseline_price and d.baseline_type
    st = d.stats
    return {
        "product_id": inp.product_id, "product_name": inp.name, "brand": inp.brand, "category": inp.category,
        "rating": inp.rating, "review_count": inp.review_count, "severity": d.severity, "score": d.score,
        "confidence": d.confidence, "history_quality": d.history_quality,
        "match_confidence": min([d.best.match_confidence, *[o.match_confidence for o in d.others]] or [100.0]),
        "best": _offer(d.best), "others": [_offer(o) for o in d.others],
        "baseline": {"type": d.baseline_type, "price": d.baseline_price, "all": d.baselines},
        "discount": d.discount, "discount_from_max": d.discount_from_max or 0.0,
        "discount_from_median": d.discount_from_median or 0.0, "discount_from_average": d.discount_from_average or 0.0,
        "stats": {"min": st.min_price, "max": st.max_price, "robust_max": st.robust_max, "median": st.median,
                  "average": st.average, "n_observations": st.n_observations, "span_days": st.span_days,
                  "volatility": st.volatility},
        "range_90d": list(d.range_90d) if d.range_90d else None,
        "trend_30d": d.trend_30d, "trend_90d": d.trend_90d, "flags": d.reasons,
        "market_discount_pct": d.market_discount_pct, "historical_best_market_price": st.min_price,
        "current_best_market_price": d.best.price, "uses_imported_history": inp.uses_imported,
        "detected_at": inp.now.astimezone(timezone.utc).isoformat(),
    }


def deliver(session: Session, event_id: int, settings: Settings | None = None) -> str:
    """Send a stored DealEvent on all configured channels. Idempotent per (event, channel).
    Raises on a transient delivery failure so the Celery task can retry with backoff."""
    s = settings or get_settings()
    event = session.get(DealEvent, event_id)
    if event is None:
        return "missing"
    errors: list[str] = []
    for channel in s.channels:
        cls = NOTIFIERS.get(channel)
        if cls is None:
            errors.append(f"unknown channel {channel}")
            continue
        note = session.scalar(select(Notification).where(
            Notification.deal_event_id == event.id, Notification.channel == channel))
        if note is None:
            note = Notification(deal_event_id=event.id, channel=channel)
            session.add(note)
            session.flush()
        if note.status == "sent":
            continue
        notifier = cls(s)  # type: ignore[call-arg]
        note.attempts += 1
        try:
            notifier.send_deal(event.details)
        except NotifierNotConfigured as exc:
            note.status, note.error = "failed", str(exc)
            log.error("notifier not configured", extra={"channel": channel})
            metrics.inc("slack_alerts_failed")
            continue
        except Exception as exc:
            note.status, note.error = "failed", str(exc)[:500]
            metrics.inc("slack_alerts_failed")
            errors.append(f"{channel}: {exc}")
            continue
        note.status, note.sent_at, note.error = "sent", datetime.now(timezone.utc), None
        metrics.inc("slack_alerts_sent")
    notes = list(session.scalars(select(Notification).where(Notification.deal_event_id == event.id)))
    event.notification_status = "sent" if notes and all(n.status == "sent" for n in notes) else "failed"
    session.flush()
    if errors:
        raise RuntimeError("; ".join(errors))
    return event.notification_status
