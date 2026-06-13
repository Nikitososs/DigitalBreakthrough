"""API classify: валидация без ONNX."""

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_classify_empty_rejected():
    res = client.post("/api/v1/classify", json={"items": []})
    assert res.status_code == 422


def test_classify_text_too_short():
    res = client.post(
        "/api/v1/classify",
        json={"items": [{"text": "ab", "group": "ЖКХ", "topic": "Вода"}]},
    )
    assert res.status_code == 422


def test_live_recent_requires_auth():
    res = client.get("/api/v1/live/recent", params={"task_id": "deadbeef"})
    assert res.status_code == 401
