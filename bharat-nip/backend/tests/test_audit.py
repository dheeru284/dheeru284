import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.audit.service import GENESIS_HASH, AuditService
from app.domain.enums import ActorType


def record(svc: AuditService, n: int):
    return svc.record(
        actor_type=ActorType.SYSTEM,
        actor_id="system:test",
        action="test.event",
        entity_type="test",
        entity_id=f"e{n}",
        payload={"n": n, "nested": {"b": 2, "a": 1}, "ratio": 0.5},
    )


def test_chain_links_and_verifies(db_session):
    svc = AuditService(db_session)
    e1, e2, e3 = (record(svc, i) for i in range(3))
    assert e1.prev_hash == GENESIS_HASH
    assert e2.prev_hash == e1.hash
    assert e3.prev_hash == e2.hash
    db_session.expire_all()  # force re-read from the database (JSONB round trip)
    result = svc.verify_chain()
    assert result.ok
    assert result.checked == 3


def test_empty_chain_verifies(db_session):
    result = AuditService(db_session).verify_chain()
    assert result.ok and result.checked == 0


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_events SET action = 'tampered'",
        "DELETE FROM audit_events",
        "TRUNCATE audit_events",
    ],
)
def test_audit_events_are_append_only(db_session, statement):
    record(AuditService(db_session), 1)
    with pytest.raises(DBAPIError, match="append-only"), db_session.begin_nested():
        db_session.execute(text(statement))


def test_tampering_is_detected(db_session):
    svc = AuditService(db_session)
    record(svc, 1)
    victim = record(svc, 2)
    record(svc, 3)
    # Simulate an attacker with superuser rights bypassing the trigger.
    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    db_session.execute(
        text("UPDATE audit_events SET payload = '{\"n\": 999}' WHERE seq = :s"),
        {"s": victim.seq},
    )
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    db_session.expire_all()
    result = svc.verify_chain()
    assert not result.ok
    assert result.first_broken_seq == victim.seq
    assert result.checked == 1


def test_verify_handles_multiple_batches(db_session):
    svc = AuditService(db_session)
    for i in range(5):
        record(svc, i)
    db_session.expire_all()
    assert svc.verify_chain(batch_size=2).checked == 5
