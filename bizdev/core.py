"""Shared helpers: audit log, rule lookup, clock."""
from __future__ import annotations

import copy
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import DEFAULT_RULES
from .models import AuditLog, AutomationRule
from .security import redact_obj

log = logging.getLogger("bizdev")


def now_utc() -> datetime:
    """Naive UTC 'now'. Tests monkeypatch `bizdev.core._clock`."""
    return _clock()


def _clock() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def set_clock(fn) -> None:
    global _clock
    _clock = fn


def audit(db: Session, actor: str, action: str, entity: str | None = None, entity_id: int | None = None,
          level: str = "info", **detail) -> None:
    db.add(AuditLog(actor=actor, action=action, entity=entity, entity_id=entity_id,
                    detail=redact_obj(detail), level=level, at=now_utc()))
    log.log(logging.WARNING if level != "info" else logging.INFO, "%s %s %s#%s", actor, action, entity, entity_id)


def get_rule(db: Session, key: str):
    row = db.scalar(select(AutomationRule).where(AutomationRule.key == key))
    return copy.deepcopy(row.value) if row else copy.deepcopy(DEFAULT_RULES.get(key))


def set_rule(db: Session, key: str, value, actor: str = "system") -> None:
    row = db.scalar(select(AutomationRule).where(AutomationRule.key == key))
    if row:
        row.value = value
    else:
        db.add(AutomationRule(key=key, value=value))
    audit(db, actor, "rule.updated", "automation_rule", None, key=key, value=value)


def ensure_default_rules(db: Session) -> None:
    for k, v in DEFAULT_RULES.items():
        if not db.scalar(select(AutomationRule).where(AutomationRule.key == k)):
            db.add(AutomationRule(key=k, value=v))
