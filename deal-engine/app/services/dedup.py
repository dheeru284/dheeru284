"""Alert de-duplication state machine (pure)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.config.settings import Settings

_SEV_RANK = {"GOOD": 1, "GREAT": 2, "EXTREME": 3}


@dataclass
class AlertSnapshot:
    active: bool = False
    last_alert_at: datetime | None = None
    last_alert_price: float | None = None
    last_alert_discount: float | None = None
    last_alert_severity: str | None = None
    last_alert_retailer: str | None = None
    miss_count: int = 0


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def should_notify(state: AlertSnapshot, price: float, discount: float, severity: str | None,
                  retailer: str, now: datetime, settings: Settings) -> tuple[bool, str]:
    last = _aware(state.last_alert_at)
    if not state.active or last is None:
        # never alerted, or the deal disappeared and has now re-appeared
        return True, "new_deal" if last is None else "deal_reappeared"
    age = now - last
    if age >= timedelta(days=settings.alert_reappear_days):
        return True, "returned_after_meaningful_period"
    if age < timedelta(hours=settings.alert_renotify_after_hours):
        return False, "within_renotify_window"
    mat = settings.alert_material_change_percent / 100.0
    if state.last_alert_price and price <= state.last_alert_price * (1 - mat):
        return True, "price_dropped_materially"
    if state.last_alert_discount is not None and discount >= state.last_alert_discount + settings.alert_material_change_percent:
        return True, "discount_improved_materially"
    if _SEV_RANK.get(severity or "", 0) > _SEV_RANK.get(state.last_alert_severity or "", 0):
        return True, "severity_upgraded"
    if state.last_alert_retailer and retailer != state.last_alert_retailer and state.last_alert_price \
            and price <= state.last_alert_price * (1 - mat):
        return True, "new_best_retailer"
    return False, "duplicate"
