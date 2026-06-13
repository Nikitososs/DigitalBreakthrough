"""CRUD пользователей."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.password import hash_password
from app.db.models import User


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)))


def create_user(db: Session, *, username: str, password: str, role: str) -> User:
    user = User(
        username=username.strip(),
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
        created_at=_now_iso(),
    )
    db.add(user)
    db.flush()
    return user


def update_user(
    db: Session,
    user: User,
    *,
    role: str | None = None,
    password: str | None = None,
    is_active: bool | None = None,
) -> User:
    if role is not None:
        user.role = role
    if password:
        user.hashed_password = hash_password(password)
    if is_active is not None:
        user.is_active = is_active
    db.add(user)
    db.flush()
    return user


def migrate_legacy_user_roles(db: Session) -> int:
    """emergency → analyst для существующих пользователей."""
    from sqlalchemy import update

    result = db.execute(
        update(User).where(User.role == "emergency").values(role="analyst")
    )
    db.flush()
    return int(result.rowcount or 0)


def ensure_admin_user(username: str, password: str, role: str = "admin") -> None:
    """Создать администратора, если его ещё нет."""
    if not username or not password:
        return
    from app.db.session import get_session

    with get_session() as session:
        if get_user_by_username(session, username):
            return
        create_user(session, username=username, password=password, role=role)
