"""Кэш геокодов в Postgres/SQLite (таблица geocode_cache)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.db.models import GeocodeCacheEntry
from app.db.session import get_session


def normalize_address_key(query: str) -> str:
    return query.strip().lower()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_geocode_entry(address_key: str) -> dict | None:
    with get_session() as session:
        row = session.get(GeocodeCacheEntry, address_key)
        if row is None:
            return None
        session.expunge(row)
        return {
            "lat": row.lat,
            "lng": row.lng,
            "display_name": row.display_name,
            "failed": bool(row.failed),
        }


def get_geocode_many(address_lines: list[str]) -> dict[str, dict]:
    keys = list({normalize_address_key(a) for a in address_lines if a and a.strip()})
    if not keys:
        return {}
    chunk = 5000
    with get_session() as session:
        out: dict[str, dict] = {}
        for i in range(0, len(keys), chunk):
            batch = keys[i : i + chunk]
            rows = session.scalars(
                select(GeocodeCacheEntry).where(GeocodeCacheEntry.address_key.in_(batch))
            ).all()
            for row in rows:
                session.expunge(row)
                out[row.address_key] = {
                    "lat": row.lat,
                    "lng": row.lng,
                    "display_name": row.display_name,
                    "failed": bool(row.failed),
                }
        return out


def set_geocode_entry(
    address_line: str,
    *,
    lat: float | None,
    lng: float | None,
    display_name: str | None = None,
    failed: bool = False,
) -> None:
    key = normalize_address_key(address_line)
    if not key:
        return
    with get_session() as session:
        row = session.get(GeocodeCacheEntry, key)
        if row is None:
            row = GeocodeCacheEntry(address_key=key, address_line=address_line.strip())
            session.add(row)
        row.address_line = address_line.strip()
        row.lat = lat
        row.lng = lng
        row.display_name = display_name
        row.failed = failed
        row.updated_at = _now_iso()


def count_geocode_cache_entries() -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(GeocodeCacheEntry)) or 0)


def import_json_cache_file(path) -> int:
    """Однократный импорт legacy geocode_cache.json в таблицу."""
    import json
    from pathlib import Path

    p = Path(path)
    if not p.is_file():
        return 0
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    if not isinstance(raw, dict) or count_geocode_cache_entries() > 0:
        return 0
    imported = 0
    for key, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        lat = entry.get("lat")
        lng = entry.get("lng")
        failed = lat is None
        set_geocode_entry(
            key,
            lat=float(lat) if lat is not None else None,
            lng=float(lng) if lng is not None else None,
            display_name=entry.get("display_name"),
            failed=failed,
        )
        imported += 1
    return imported
