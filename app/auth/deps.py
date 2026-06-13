"""FastAPI-зависимости: текущий пользователь и проверка прав."""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.auth.permissions import Permission, role_has_permission
from app.db.models import User
from app.db.session import get_session
from app.db.user_repo import get_user_by_username

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    with get_session() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется авторизация")
    try:
        payload = decode_access_token(creds.credentials)
        username = payload.get("sub")
        if not username:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недействительный токен")
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недействительный токен") from exc

    user = get_user_by_username(db, username)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Пользователь не найден")
    return user


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Учётная запись отключена")
    return user


CurrentUser = Annotated[User, Depends(get_current_active_user)]


def require_permission(*permissions: Permission) -> Callable:
    needed = set(permissions)

    async def _checker(user: User = Depends(get_current_active_user)) -> User:
        if any(role_has_permission(user.role, perm) for perm in needed):
            return user
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостаточно прав")

    return _checker
