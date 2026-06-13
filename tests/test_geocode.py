"""Тесты геокодера."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.db.geocode_cache_repo import get_geocode_entry, normalize_address_key, set_geocode_entry
from app.db.session import init_db
from app.geocode import geocode_address


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def test_geocode_uses_db_cache():
    query = "Омск, ул. Ленина"
    set_geocode_entry(query, lat=54.99, lng=73.36, failed=False)
    coords = geocode_address(query)
    assert coords == (54.99, 73.36)


def test_geocode_queries_nominatim():
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps([{"lat": "55.01", "lon": "73.37"}]).encode()

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        coords = geocode_address("ул. Тестовая, Омск, Омская область, Россия")

    assert coords == (55.01, 73.37)
    key = normalize_address_key("ул. Тестовая, Омск, Омская область, Россия")
    saved = get_geocode_entry(key)
    assert saved is not None
    assert saved["lat"] == 55.01


def test_geocode_marks_failed_on_error():
    with patch("urllib.request.urlopen", side_effect=OSError("network")):
        coords = geocode_address("ул. Ошибка, Омск, Омская область, Россия")
    assert coords is None
    key = normalize_address_key("ул. Ошибка, Омск, Омская область, Россия")
    saved = get_geocode_entry(key)
    assert saved is not None
    assert saved.get("failed") is True
