"""JWT-авторизация и роли."""

from app.auth.deps import get_current_active_user, get_current_user, require_permission
from app.auth.permissions import Permission, Role, role_has_permission

__all__ = [
    "Permission",
    "Role",
    "get_current_active_user",
    "get_current_user",
    "require_permission",
    "role_has_permission",
]
