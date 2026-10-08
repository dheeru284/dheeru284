from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config.settings import get_settings
from app.utils.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

celery = Celery("dealengine", broker=settings.redis_url, backend=settings.redis_url,
                include=["app.workers.discovery", "app.workers.crawling", "app.workers.matching",
                         "app.workers.alerts", "app.workers.maintenance"])
celery.conf.update(
    task_serializer="json", accept_content=["json"], result_expires=3600, timezone="UTC",
    task_acks_late=True, worker_prefetch_multiplier=1, task_reject_on_worker_lost=True,
    task_routes={
        "app.workers.discovery.*": {"queue": "discovery"},
        "app.workers.crawling.crawl_product": {"queue": "crawl"},
        "app.workers.alerts.*": {"queue": "alerts"},
    },
    task_default_queue="default",
    beat_schedule={
        "schedule-crawls": {"task": "app.workers.crawling.schedule_crawls",
                            "schedule": settings.scheduler_tick_minutes * 60.0},
        "discover-all": {"task": "app.workers.discovery.discover_all",
                         "schedule": settings.discovery_interval_hours * 3600.0},
        "aggregate-history": {"task": "app.workers.maintenance.aggregate_history",
                              "schedule": crontab(hour=2, minute=15)},
        "cleanup": {"task": "app.workers.maintenance.cleanup", "schedule": crontab(hour=3, minute=30)},
        "refresh-fx": {"task": "app.workers.maintenance.refresh_fx",
                       "schedule": settings.fx_cache_ttl_hours * 3600.0},
        "retry-failed-alerts": {"task": "app.workers.alerts.retry_pending_alerts", "schedule": 900.0},
    },
)

# Retry policy: 30s -> 2min -> 10min, then give up and record the failure.
RETRY_COUNTDOWNS = (30, 120, 600)
