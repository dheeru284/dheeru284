from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.core.security import hash_password, verify_password
from app.domain.enums import ActorType, UserRole
from app.models import User
from app.services.errors import Conflict, NotFound


def actor_for(user: User | None) -> tuple[ActorType, str]:
    return (ActorType.USER, str(user.id)) if user else (ActorType.SYSTEM, "system:cli")


def create_user(
    session: Session,
    *,
    email: str,
    display_name: str,
    role: UserRole,
    password: str,
    created_by: User | None,
) -> User:
    email = email.strip().lower()
    if session.scalar(select(User).where(User.email == email)):
        raise Conflict(f"A user with email {email} already exists.")
    user = User(
        email=email, display_name=display_name, role=role, password_hash=hash_password(password)
    )
    session.add(user)
    session.flush()
    actor_type, actor_id = actor_for(created_by)
    AuditService(session).record(
        actor_type=actor_type,
        actor_id=actor_id,
        action="user.created",
        entity_type="user",
        entity_id=user.id,
        payload={"email": email, "role": role.value},
    )
    return user


def authenticate(session: Session, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user


def update_user(
    session: Session,
    user_id: uuid.UUID,
    *,
    role: UserRole | None,
    is_active: bool | None,
    actor: User,
) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("User not found.")
    changes: dict[str, object] = {}
    if role is not None and role != user.role:
        changes["role"] = {"from": user.role.value, "to": role.value}
        user.role = role
    if is_active is not None and is_active != user.is_active:
        changes["is_active"] = {"from": user.is_active, "to": is_active}
        user.is_active = is_active
    if changes:
        session.flush()
        AuditService(session).record(
            actor_type=ActorType.USER,
            actor_id=str(actor.id),
            action="user.updated",
            entity_type="user",
            entity_id=user.id,
            payload=changes,
        )
    return user
