"""Роли и матрица прав."""

from __future__ import annotations

from enum import Enum

# Устаревшая роль emergency → analyst (миграция users + JWT).
LEGACY_ROLE_ALIASES: dict[str, str] = {
    "emergency": "analyst",
}


class Role(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    OPERATOR = "operator"


class Permission(str, Enum):
    USERS_MANAGE = "users.manage"
    JOBS_UPLOAD = "jobs.upload"
    JOBS_READ = "jobs.read"
    ARCHIVE_READ = "archive.read"
    ARCHIVE_WRITE = "archive.write"
    DASHBOARD = "dashboard.read"
    REPORTS = "reports.read"
    INCIDENTS_READ = "incidents.read"
    INCIDENTS_WRITE = "incidents.write"
    GEOCODE_WARMUP = "geocode.warmup"
    LIVE_READ = "live.read"
    OPERATOR_EMAIL = "operator.email"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),
    Role.ANALYST: {
        Permission.JOBS_READ,
        Permission.ARCHIVE_READ,
        Permission.DASHBOARD,
        Permission.REPORTS,
        Permission.INCIDENTS_READ,
        Permission.LIVE_READ,
        Permission.GEOCODE_WARMUP,
    },
    Role.OPERATOR: {
        Permission.JOBS_READ,
        Permission.ARCHIVE_READ,
        Permission.INCIDENTS_READ,
        Permission.INCIDENTS_WRITE,
        Permission.LIVE_READ,
        Permission.OPERATOR_EMAIL,
    },
}


def normalize_role(role: str) -> str:
    value = (role or "").strip()
    return LEGACY_ROLE_ALIASES.get(value, value)


def _parse_role(role: str) -> Role | None:
    try:
        return Role(normalize_role(role))
    except ValueError:
        return None


def role_has_permission(role: str, permission: Permission) -> bool:
    parsed = _parse_role(role)
    if parsed is None:
        return False
    return permission in ROLE_PERMISSIONS.get(parsed, set())


def allowed_dashboard_roles(role: str) -> list[str]:
    """Роли UI дашборда, доступные пользователю."""
    parsed = _parse_role(role)
    if parsed is Role.ADMIN:
        return [Role.ANALYST.value, Role.OPERATOR.value]
    if parsed is Role.ANALYST:
        return [Role.ANALYST.value]
    if parsed is Role.OPERATOR:
        return [Role.OPERATOR.value]
    return []
