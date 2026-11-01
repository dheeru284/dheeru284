"""Authentication and role checks as FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings_dep
from app.core.config import Settings
from app.core.security import InvalidToken, decode_access_token
from app.domain.enums import ROLE_RANK, UserRole
from app.models import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid access token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        user_id = decode_access_token(credentials.credentials, settings)
    except InvalidToken:
        raise unauthorized from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_role(minimum: UserRole) -> Callable[[User], User]:
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if ROLE_RANK[user.role] < ROLE_RANK[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role {minimum.value} or higher.",
            )
        return user

    return dependency


def has_role(user: User, minimum: UserRole) -> bool:
    return ROLE_RANK[user.role] >= ROLE_RANK[minimum]


CurrentUser = Annotated[User, Depends(get_current_user)]
Analyst = Annotated[User, Depends(require_role(UserRole.ANALYST))]
Reviewer = Annotated[User, Depends(require_role(UserRole.REVIEWER))]
Admin = Annotated[User, Depends(require_role(UserRole.ADMIN))]
