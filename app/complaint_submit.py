"""Приём новых обращений граждан: ONNX + геокод + БД + live-поток."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.address import geocode_query_from_row, has_street_address
from app.agency_mapping import resolve_agency, resolve_agency_email, resolve_municipality_admin
from app.classify_service import classify_appeals
from app.db.repository import (
    insert_citizen_complaint_row,
    list_recent_citizen_complaints,
    utc_iso_z,
)
from app.constants import CITIZEN_ROW_PREFIX
from app.geocode import geocode_address
from app.report import severity_label


def submit_citizen_complaint(
    task_id: str,
    *,
    text: str,
    group: str,
    topic: str,
    municipality: str,
    settlement: str = "",
    street: str = "",
    house: str = "",
    geocode_cache: Path | None = None,
) -> dict:
    body = str(text or "").strip()
    if len(body) < 10:
        raise ValueError("Текст обращения слишком короткий (минимум 10 символов)")
    muni = str(municipality or "").strip()
    if not muni:
        raise ValueError("Укажите муниципалитет")

    group = str(group or "").strip()
    topic = str(topic or "").strip()
    settlement = str(settlement or "").strip()
    street = str(street or "").strip()
    house = str(house or "").strip()

    payload = {"group": group, "topic": topic, "text": body}
    results, latency_ms = classify_appeals([payload])
    hit = results[0]

    row_dict = {
        "муниципалитет": muni,
        "населенный_пункт": settlement,
        "улица": street,
        "дом": house,
    }
    address_line, _ = geocode_query_from_row(row_dict)
    has_address = has_street_address(row_dict)
    lat = lng = None
    if has_address and geocode_cache is not None:
        coords = geocode_address(address_line, geocode_cache)
        if coords:
            lat, lng = coords

    agency = resolve_agency(group)
    admin = resolve_municipality_admin(muni)
    now = utc_iso_z()
    row_id = f"{CITIZEN_ROW_PREFIX}{uuid.uuid4().hex[:12]}"

    incident_row = {
        "task_id": task_id,
        "row_id": row_id,
        "created_at": now,
        "group_name": group,
        "topic": topic,
        "municipality": muni,
        "settlement": settlement or None,
        "street": street or None,
        "house": house or None,
        "text": body,
        "severity": int(hit.severity),
        "is_problem": bool(hit.is_problem),
        "agency": agency,
        "agency_email": resolve_agency_email(agency),
        "municipality_admin": admin.get("administration"),
        "municipality_email": admin.get("email"),
        "municipality_phone": admin.get("phone"),
        "address_line": address_line,
        "has_address": has_address,
        "lat": lat,
        "lng": lng,
    }
    insert_citizen_complaint_row(incident_row)

    return {
        "id": row_id,
        "severity": hit.severity,
        "label": hit.label or severity_label(hit.severity),
        "confidence": hit.confidence,
        "is_problem": hit.is_problem,
        "municipality": muni,
        "settlement": settlement or None,
        "street": street or None,
        "house": house or None,
        "has_address": has_address,
        "lat": lat,
        "lng": lng,
        "group": group,
        "topic": topic,
        "text": body[:500],
        "created_at": now,
        "agency": agency,
        "agency_email": resolve_agency_email(agency),
        "municipality_admin": admin.get("administration"),
        "municipality_email": admin.get("email"),
        "municipality_phone": admin.get("phone"),
        "task_id": task_id,
        "latency_ms": round(latency_ms, 1),
        "source": "citizen",
    }


def recent_citizen_events(
    task_id: str | None = None,
    *,
    since: str | None = None,
    limit: int = 20,
) -> list[dict]:
    rows = list_recent_citizen_complaints(task_id, since=since, limit=limit)
    events = []
    for row in rows:
        events.append({
            "id": row.row_id,
            "severity": int(row.severity),
            "label": severity_label(row.severity),
            "confidence": 1.0,
            "is_problem": bool(row.is_problem),
            "municipality": row.municipality or "",
            "settlement": row.settlement,
            "street": row.street,
            "house": row.house,
            "has_address": bool(row.has_address),
            "lat": row.lat,
            "lng": row.lng,
            "group": row.group_name or "",
            "topic": row.topic or "",
            "text": (row.text or "")[:500],
            "created_at": row.created_at,
            "agency": row.agency or "",
            "agency_email": row.agency_email,
            "municipality_admin": row.municipality_admin,
            "municipality_email": row.municipality_email,
            "municipality_phone": row.municipality_phone,
            "task_id": row.task_id,
            "latency_ms": 0.0,
            "source": "citizen",
        })
    return events
