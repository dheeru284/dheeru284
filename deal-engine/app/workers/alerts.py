from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select

from app.database.session import session_scope
from app.models.deal import DealEvent
from app.services import notification_service
from app.utils.logging import get_logger
from app.workers.celery_app import RETRY_COUNTDOWNS, celery

log = get_logger(__name__)


@celery.task(name="app.workers.alerts.send_slack_alert", bind=True, max_retries=len(RETRY_COUNTDOWNS))
def send_slack_alert(self, event_id: int) -> str:  # type: ignore[no-untyped-def]
    """Deliver a stored DealEvent on all configured channels. Idempotent: sent channels are skipped."""
    with session_scope() as session:
        try:
            return notification_service.deliver(session, event_id)
        except Exception as exc:
            session.commit()  # keep the failed-attempt bookkeeping
            if self.request.retries >= self.max_retries:
                log.error("alert delivery gave up", extra={"event_id": event_id, "error": str(exc)})
                return "failed"
            raise self.retry(exc=exc, countdown=RETRY_COUNTDOWNS[self.request.retries]) from exc


@celery.task(name="app.workers.alerts.retry_pending_alerts")
def retry_pending_alerts() -> int:
    """Safety net: re-queue events whose delivery task was lost (worker crash, Redis flush) and events that
    failed in the last 24 h (e.g. Slack outage). Sent channels are skipped, so this cannot double-post."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    with session_scope() as session:
        ids = list(session.scalars(
            select(DealEvent.id)
            .where(or_(DealEvent.notification_status == "pending",
                       and_(DealEvent.notification_status == "failed", DealEvent.detected_at >= cutoff)))
            .order_by(DealEvent.id).limit(50)))
    for i in ids:
        send_slack_alert.apply_async(args=[i], queue="alerts")
    return len(ids)
