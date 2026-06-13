"""API авторизации: login, защищённые маршруты, CRUD пользователей."""

import os
import uuid
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "adminpass123")

from app.db.session import init_db
from src.main import app

init_db()

client = TestClient(app)


def _login(username: str = "admin", password: str = "adminpass123") -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_success():
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "adminpass123"})
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "admin"
    assert body["user"]["role"] == "admin"
    assert body["access_token"]


def test_login_wrong_password():
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert res.status_code == 401


def test_protected_route_without_token():
    res = client.get("/api/v1/jobs")
    assert res.status_code == 401


def test_public_health_and_classify_still_open():
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/reference/facets").status_code == 200


def test_me_with_token():
    token = _login()
    res = client.get("/api/v1/auth/me", headers=_auth_headers(token))
    assert res.status_code == 200
    assert res.json()["username"] == "admin"


def test_admin_user_crud():
    token = _login()
    headers = _auth_headers(token)
    username = f"pytest_analyst_{uuid.uuid4().hex[:8]}"

    create = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": username, "password": "secret12", "role": "analyst"},
    )
    assert create.status_code == 201, create.text
    user_id = create.json()["id"]

    listed = client.get("/api/v1/users", headers=headers)
    assert listed.status_code == 200
    assert any(u["username"] == username for u in listed.json())

    patch = client.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"role": "operator"},
    )
    assert patch.status_code == 200
    assert patch.json()["role"] == "operator"

    deactivate = client.delete(f"/api/v1/users/{user_id}", headers=headers)
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False


def test_non_admin_cannot_list_users():
    token = _login()
    headers = _auth_headers(token)
    username = f"pytest_op_{uuid.uuid4().hex[:8]}"
    create = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": username, "password": "secret12", "role": "operator"},
    )
    assert create.status_code == 201
    op_token = _login(username, "secret12")
    res = client.get("/api/v1/users", headers=_auth_headers(op_token))
    assert res.status_code == 403
