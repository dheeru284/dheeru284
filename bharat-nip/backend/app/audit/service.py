"""Append-only, hash-chained audit log (DATABASE_DESIGN.md §3.18, SECURITY.md §4).

``record`` must be called inside the same transaction as the change it
describes, so both commit or roll back together.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.hashing import canonical_json, sha256_text
from app.domain.enums import ActorType
from app.models.audit import AuditEvent

GENESIS_HASH = "0" * 64
# Arbitrary constant key for pg_advisory_xact_lock; serialises appends so the chain is linear.
AUDIT_LOCK_KEY = 0x424E4950  # "BNIP"


def compute_event_hash(
    prev_hash: str,
    *,
    event_id: uuid.UUID,
    occurred_at: datetime,
    actor_type: ActorType | str,
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any],
) -> str:
    fields = {
        "id": str(event_id),
        "occurred_at": occurred_at.astimezone(UTC).isoformat(),
        "actor_type": str(actor_type),
        "actor_id": actor_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "payload": payload,
    }
    return sha256_text(prev_hash + canonical_json(fields))


@dataclass(frozen=True)
class ChainVerification:
    ok: bool
    checked: int
    first_broken_seq: int | None


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        actor_type: ActorType,
        actor_id: str,
        action: str,
        entity_type: str,
        entity_id: str | uuid.UUID,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        self.session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": AUDIT_LOCK_KEY})
        prev_hash = self.session.scalar(
            select(AuditEvent.hash).order_by(AuditEvent.seq.desc()).limit(1)
        )
        prev_hash = prev_hash or GENESIS_HASH
        # Normalise the payload to pure JSON so the hash survives the JSONB round trip.
        normalized = json.loads(canonical_json(payload or {}))
        event_id = uuid.uuid4()
        occurred_at = datetime.now(UTC)
        entity_id_str = str(entity_id)
        event = AuditEvent(
            id=event_id,
            occurred_at=occurred_at,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id_str,
            payload=normalized,
            prev_hash=prev_hash,
            hash=compute_event_hash(
                prev_hash,
                event_id=event_id,
                occurred_at=occurred_at,
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id_str,
                payload=normalized,
            ),
        )
        self.session.add(event)
        self.session.flush()
        return event

    def verify_chain(self, batch_size: int = 1000) -> ChainVerification:
        expected_prev = GENESIS_HASH
        checked = 0
        last_seq = 0
        while True:
            rows = self.session.scalars(
                select(AuditEvent)
                .where(AuditEvent.seq > last_seq)
                .order_by(AuditEvent.seq)
                .limit(batch_size)
            ).all()
            if not rows:
                return ChainVerification(ok=True, checked=checked, first_broken_seq=None)
            for ev in rows:
                recomputed = compute_event_hash(
                    ev.prev_hash,
                    event_id=ev.id,
                    occurred_at=ev.occurred_at,
                    actor_type=ev.actor_type,
                    actor_id=ev.actor_id,
                    action=ev.action,
                    entity_type=ev.entity_type,
                    entity_id=ev.entity_id,
                    payload=ev.payload,
                )
                if ev.prev_hash != expected_prev or recomputed != ev.hash:
                    return ChainVerification(ok=False, checked=checked, first_broken_seq=ev.seq)
                expected_prev = ev.hash
                checked += 1
                last_seq = ev.seq
