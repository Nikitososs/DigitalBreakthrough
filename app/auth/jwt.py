"""Создание и проверка JWT access-токенов."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))


def _secret() -> str:
    secret = os.environ.get("JWT_SECRET", "").strip()
    if not secret:
        secret = "dev-insecure-change-me"
    return secret


def create_access_token(subject: str, *, role: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
