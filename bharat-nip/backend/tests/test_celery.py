from app.workers.celery_app import celery_app
from app.workers.tasks import ping


def test_ping_task_registered_and_runs_eagerly():
    assert "system.ping" in celery_app.tasks
    assert ping.apply().get() == "pong"


def test_celery_reliability_settings():
    conf = celery_app.conf
    assert conf.task_acks_late is True
    assert conf.worker_prefetch_multiplier == 1
    assert conf.task_serializer == "json"
