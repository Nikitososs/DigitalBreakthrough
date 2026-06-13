"""Единый формат карточки обращения (incident) для API.

Источники разные — ORM-строка StoredIncident (БД) и pandas-строка (parquet) —
но карточка одна. Раньше форма дублировалась в repository._incident_to_api и
task_incidents._row_to_incident; теперь живёт здесь в одном месте.
"""

from __future__ import annotations


def incident_payload(
    *,
    id: str,
    text: str,
    severity: int,
    label: str,
    municipality: str,
    settlement: str | None,
    street: str | None,
    house: str | None,
    address: str,
    has_address: bool,
    lat: float | None,
    lng: float | None,
    group: str,
    topic: str,
    agency: str,
    agency_email: str | None,
    municipality_admin: str | None,
    municipality_email: str | None,
    municipality_phone: str | None,
    created_at: str | None,
    incident_number: str | None = None,
    closed_at: str | None = None,
    workflow_step: str | None = None,
    outcome: str | None = None,
    manually_resolved: bool = False,
    resolved_at: str | None = None,
    resolved_note: str | None = None,
) -> dict:
    """Собирает словарь карточки обращения в форме, ожидаемой схемой TaskIncidentItem."""
    return {
        "id": id,
        "text": text,
        "severity": severity,
        "label": label,
        "municipality": municipality,
        "settlement": settlement,
        "street": street,
        "house": house,
        "address": address,
        "has_address": has_address,
        "lat": lat,
        "lng": lng,
        "group": group,
        "topic": topic,
        "agency": agency,
        "agency_email": agency_email,
        "municipality_admin": municipality_admin,
        "municipality_email": municipality_email,
        "municipality_phone": municipality_phone,
        "created_at": created_at,
        "incident_number": incident_number,
        "closed_at": closed_at,
        "workflow_step": workflow_step,
        "outcome": outcome,
        "manually_resolved": manually_resolved,
        "resolved_at": resolved_at,
        "resolved_note": resolved_note,
    }
