"""Управление пользователями (только admin)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import get_db, require_permission
from app.auth.permissions import Permission, Role
from app.db.user_repo import create_user, get_user_by_id, list_users, update_user
from schemas import UserCreateRequest, UserPublic, UserUpdateRequest

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_permission(Permission.USERS_MANAGE))],
)


def _to_public(user) -> UserPublic:
    return UserPublic(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
    )


def _validate_role(role: str) -> str:
    try:
        Role(role)
    except ValueError as exc:
        raise HTTPException(400, "Роль: admin, analyst, operator") from exc
    return role


@router.get("", response_model=list[UserPublic], summary="Список пользователей")
async def get_users(db: Session = Depends(get_db)):
    return [_to_public(u) for u in list_users(db)]


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED, summary="Создать пользователя")
async def post_user(body: UserCreateRequest, db: Session = Depends(get_db)):
    role = _validate_role(body.role)
    try:
        user = create_user(db, username=body.username, password=body.password, role=role)
    except IntegrityError as exc:
        raise HTTPException(409, "Пользователь с таким именем уже существует") from exc
    return _to_public(user)


@router.patch("/{user_id}", response_model=UserPublic, summary="Изменить роль / пароль / активность")
async def patch_user(user_id: int, body: UserUpdateRequest, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Пользователь не найден")
    role = _validate_role(body.role) if body.role is not None else None
    return _to_public(
        update_user(
            db,
            user,
            role=role,
            password=body.password,
            is_active=body.is_active,
        )
    )


@router.delete("/{user_id}", response_model=UserPublic, summary="Отключить пользователя")
async def deactivate_user(user_id: int, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Пользователь не найден")
    return _to_public(update_user(db, user, is_active=False))
