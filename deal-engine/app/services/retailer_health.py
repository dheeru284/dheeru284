"""Per-retailer circuit breaker: a retailer that blocks or keeps failing is paused; others continue."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.models.retailer import Retailer
from app.services import metrics
from app.utils.logging import get_logger

log = get_logger(__name__)


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_available(retailer: Retailer, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if not retailer.active or retailer.status == "unconfigured":
        return False
    until = _aware(retailer.unavailable_until)
    return not (retailer.status in ("unavailable", "degraded") and until and until > now)


def record_success(session: Session, retailer: Retailer) -> None:
    retailer.consecutive_failures = 0
    retailer.last_success_at = datetime.now(timezone.utc)
    if retailer.status in ("degraded", "unavailable"):
        retailer.status, retailer.status_reason, retailer.unavailable_until = "ok", None, None


def record_failure(session: Session, retailer: Retailer, reason: str, blocked: bool = False,
                   settings: Settings | None = None) -> None:
    s = settings or get_settings()
    now = datetime.now(timezone.utc)
    retailer.last_failure_at = now
    retailer.consecutive_failures += 1
    retailer.status_reason = reason[:500]
    if blocked:
        retailer.status = "unavailable"
        retailer.unavailable_until = now + timedelta(hours=s.retailer_block_cooldown_hours)
        metrics.inc("retailer_blocked", retailer=retailer.key)
        log.warning("retailer paused: automated access refused", extra={"retailer": retailer.key, "reason": reason})
    elif retailer.consecutive_failures >= s.retailer_failure_threshold:
        retailer.status = "degraded"
        retailer.unavailable_until = now + timedelta(minutes=30)


def get_retailer(session: Session, key: str) -> Retailer | None:
    return session.scalar(select(Retailer).where(Retailer.key == key))
