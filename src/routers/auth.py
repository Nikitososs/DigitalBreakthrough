"""Вход в систему и профиль текущего пользователя."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, get_db
from app.auth.jwt import create_access_token
from app.auth.password import verify_password
from app.auth.permissions import Role, allowed_dashboard_roles, normalize_role
from app.db.user_repo import get_user_by_username
from schemas import LoginRequest, LoginResponse, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, summary="Вход (JWT)")
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(db, body.username.strip())
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Учётная запись отключена")

    token = create_access_token(user.username, role=normalize_role(user.role))
    return LoginResponse(
        access_token=token,
        user=UserPublic(
            id=user.id,
            username=user.username,
            role=normalize_role(user.role),
            is_active=user.is_active,
        ),
    )


@router.get("/me", response_model=UserPublic, summary="Текущий пользователь")
async def me(user: CurrentUser):
    return UserPublic(
        id=user.id,
        username=user.username,
        role=normalize_role(user.role),
        is_active=user.is_active,
    )


@router.get("/roles", summary="Доступные роли UI для текущего пользователя")
async def my_dashboard_roles(user: CurrentUser):
    roles = allowed_dashboard_roles(user.role)
    if normalize_role(user.role) == Role.ADMIN.value:
        roles = [Role.ADMIN.value, *roles]
    return {"role": normalize_role(user.role), "dashboard_roles": roles}
