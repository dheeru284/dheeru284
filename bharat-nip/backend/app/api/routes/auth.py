from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import Admin, CurrentUser
from app.api.deps import get_db, get_settings_dep
from app.core.config import Settings
from app.core.security import create_access_token
from app.models import User
from app.schemas.api import TokenRequest, TokenResponse, UserCreate, UserOut, UserUpdate
from app.services.users import authenticate, create_user, update_user

router = APIRouter(tags=["auth"])
DB = Annotated[Session, Depends(get_db)]


@router.post("/auth/token", response_model=TokenResponse)
def login(body: TokenRequest, db: DB, settings: Annotated[Settings, Depends(get_settings_dep)]):
    user = authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")
    token, expires_in = create_access_token(user.id, settings)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/auth/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(_: Admin, db: DB):
    return db.scalars(select(User).order_by(User.created_at)).all()


@router.post("/users", response_model=UserOut, status_code=201)
def add_user(body: UserCreate, admin: Admin, db: DB):
    user = create_user(
        db,
        email=body.email,
        display_name=body.display_name,
        role=body.role,
        password=body.password,
        created_by=admin,
    )
    db.commit()
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def patch_user(user_id: uuid.UUID, body: UserUpdate, admin: Admin, db: DB):
    user = update_user(db, user_id, role=body.role, is_active=body.is_active, actor=admin)
    db.commit()
    return user
