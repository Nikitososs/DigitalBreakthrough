"""Геокодирование адресов (Nominatim) с кэшем в Postgres/SQLite."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from app.db.geocode_cache_repo import (
    get_geocode_entry,
    normalize_address_key,
    set_geocode_entry,
)

USER_AGENT = os.environ.get("NOMINATIM_USER_AGENT", "ZeroProblemsHackaton/1.0 (omsk-incidents)")
NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "http://nominatim:8080").rstrip("/")
NOMINATIM_MIN_INTERVAL_SEC = max(0.0, float(os.environ.get("NOMINATIM_MIN_INTERVAL_SEC", "0")))
NOMINATIM_CONCURRENCY = max(1, int(os.environ.get("NOMINATIM_CONCURRENCY", "8")))
OMSK_CITY_VIEWBOX = "73.20,55.15,73.58,54.82"
_geocode_semaphore = threading.Semaphore(NOMINATIM_CONCURRENCY)
_rate_lock = threading.Lock()
_last_request_at = 0.0


def _targets_omsk_city(query: str) -> bool:
    key = query.strip().lower()
    return (
        ", омск," in key
        or key.endswith(", омск")
        or key.endswith(", омск, омская область, россия")
    )


_OMSK_REGION_SUFFIX = ", омская область, россия"


def _nominatim_search_query(query: str) -> str:
    """Упрощает строку адреса из выгрузки для поиска в Nominatim."""
    q = query.strip()
    low = q.lower()
    if low.endswith(_OMSK_REGION_SUFFIX):
        q = q[: -len(_OMSK_REGION_SUFFIX)].strip().rstrip(",")
    q = re.sub(r"(?i)\bул\.\s*", "", q)
    q = re.sub(r"(?i)\bпр\.\s*", "", q)
    q = re.sub(r"(?i)\bпер\.\s*", "", q)
    q = re.sub(r"(?i)\bд\.\s*", "", q)
    q = re.sub(r"\s*,\s*", ", ", q)
    q = re.sub(r"\s+", " ", q).strip(" ,")
    return q


def _nominatim_search_params(query: str) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "q": query,
        "format": "json",
        "limit": 5 if _targets_omsk_city(query) else 1,
        "countrycodes": "ru",
        "addressdetails": 1,
    }
    if _targets_omsk_city(query):
        params["viewbox"] = OMSK_CITY_VIEWBOX
        params["bounded"] = 1
    return params


def _pick_best_result(items: list[dict], query: str) -> dict | None:
    if not items:
        return None
    if not _targets_omsk_city(query):
        return items[0]
    for item in items:
        addr = item.get("address") or {}
        city = str(addr.get("city") or addr.get("town") or "").lower()
        if city == "омск" or "омск" in city:
            return item
        display = str(item.get("display_name") or "").lower()
        if "омск" in display and "полтавка" not in display:
            return item
    return items[0]


def _entry_to_coords(entry: dict | None) -> tuple[float, float] | None:
    if not entry:
        return None
    if entry.get("failed") or entry.get("lat") is None:
        return None
    return float(entry["lat"]), float(entry["lng"])


def _persist_entry(query: str, entry: dict, *, cache: dict[str, dict] | None, cache_dirty: list[bool] | None) -> None:
    key = normalize_address_key(query)
    lat = entry.get("lat")
    lng = entry.get("lng")
    failed = lat is None
    set_geocode_entry(
        query,
        lat=float(lat) if lat is not None else None,
        lng=float(lng) if lng is not None else None,
        display_name=entry.get("display_name"),
        failed=failed,
    )
    if cache is not None:
        cache[key] = entry
        if cache_dirty is not None:
            cache_dirty[0] = True


def _lookup_entry(key: str, cache: dict[str, dict] | None) -> dict | None:
    if cache is not None and key in cache:
        return cache[key]
    return get_geocode_entry(key)


def geocode_address(
    query: str,
    cache_path: Path | None = None,
    *,
    timeout: float = 8.0,
    cache_only: bool = False,
    force_fresh: bool = False,
    cache: dict[str, dict] | None = None,
    cache_dirty: list[bool] | None = None,
    fresh_budget: list[int] | None = None,
) -> tuple[float, float] | None:
    """Возвращает [lat, lng] или None. Кэш хранится в таблице geocode_cache."""
    del cache_path  # legacy param, kept for API compatibility
    key = normalize_address_key(query)
    if not key:
        return None

    hit = _lookup_entry(key, cache)
    if hit and not force_fresh:
        return _entry_to_coords(hit)

    if cache_only:
        return None

    if fresh_budget is not None and fresh_budget[0] <= 0:
        return None

    with _geocode_semaphore:
        global _last_request_at
        if NOMINATIM_MIN_INTERVAL_SEC > 0:
            with _rate_lock:
                elapsed = time.time() - _last_request_at
                if elapsed < NOMINATIM_MIN_INTERVAL_SEC:
                    time.sleep(NOMINATIM_MIN_INTERVAL_SEC - elapsed)

        search_query = _nominatim_search_query(query)
        params = urllib.parse.urlencode(_nominatim_search_params(search_query))
        url = f"{NOMINATIM_URL}/search?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

        if fresh_budget is not None:
            fresh_budget[0] -= 1

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            entry = {"lat": None, "lng": None, "failed": True}
            _persist_entry(query, entry, cache=cache, cache_dirty=cache_dirty)
            return None
        finally:
            if NOMINATIM_MIN_INTERVAL_SEC > 0:
                with _rate_lock:
                    _last_request_at = time.time()

        if not data:
            entry = {"lat": None, "lng": None, "failed": True}
            _persist_entry(query, entry, cache=cache, cache_dirty=cache_dirty)
            return None

        best = _pick_best_result(data, query)
        if best is None:
            entry = {"lat": None, "lng": None, "failed": True}
            _persist_entry(query, entry, cache=cache, cache_dirty=cache_dirty)
            return None

        lat = float(best["lat"])
        lng = float(best["lon"])
        entry: dict = {"lat": lat, "lng": lng, "failed": False}
        display = best.get("display_name")
        if display:
            entry["display_name"] = display
        _persist_entry(query, entry, cache=cache, cache_dirty=cache_dirty)
        return lat, lng


# Legacy helpers — делегируют в geocode_cache_repo (для совместимости импортов).
def _load_cache(path: Path) -> dict[str, dict]:
    del path
    return {}


def _save_cache(path: Path, cache: dict[str, dict]) -> None:
    del path
    for key, entry in cache.items():
        if not isinstance(entry, dict):
            continue
        set_geocode_entry(
            key,
            lat=entry.get("lat"),
            lng=entry.get("lng"),
            display_name=entry.get("display_name"),
            failed=entry.get("lat") is None,
        )
