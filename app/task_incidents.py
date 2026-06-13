"""Список обращений задачи для режимов Оператор / Экстренный."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.address import geocode_query_from_row, has_street_address
from app.agency_mapping import resolve_agency, resolve_agency_email, resolve_municipality_admin
from app.incidents import incident_payload

_SEARCH_COLUMNS = ("текст", "тема", "улица", "населенный_пункт", "муниципалитет", "группа")
from app.db.repository import (
    has_incidents_in_db,
    has_stored_job,
    list_facets_from_db,
    list_incident_packages_from_db,
    list_incidents_from_db,
    list_map_markers_from_db,
)
from app.db.geocode_cache_repo import get_geocode_many
from app.geocode import geocode_address
from app.live_feed import load_labeled_pool
from app.incident_packages import build_agency_packages
from app.report import severity_label
from app.resolved import is_resolved_row
from app.report_dates import _parse_report_date


def _row_to_incident(
    row: pd.Series,
    *,
    geocode: bool = False,
    geocode_cache: Path | None = None,
    geocode_cache_only: bool = False,
    shared_geocode_cache: dict[str, dict] | None = None,
    geocode_cache_dirty: list[bool] | None = None,
    geocode_fresh_budget: list[int] | None = None,
) -> dict:
    municipality = str(row.get("муниципалитет", "")).strip()
    settlement = str(row.get("населенный_пункт", "")).strip()
    street = str(row.get("улица", "")).strip()
    house = str(row.get("дом", "")).strip()
    group = str(row.get("группа", "")).strip()
    topic = str(row.get("тема", "")).strip()
    try:
        severity = int(row.get("severity", 0))
    except (TypeError, ValueError):
        severity = 0

    agency = resolve_agency(group)
    admin = resolve_municipality_admin(municipality)
    row_dict = {
        "муниципалитет": municipality,
        "населенный_пункт": settlement,
        "улица": street,
        "дом": house,
    }
    address_line, has_address = geocode_query_from_row(row_dict)
    lat = lng = None
    if geocode and has_address and geocode_cache is not None:
        coords = geocode_address(
            address_line,
            geocode_cache,
            cache_only=geocode_cache_only,
            cache=shared_geocode_cache,
            cache_dirty=geocode_cache_dirty,
            fresh_budget=geocode_fresh_budget,
        )
        if coords:
            lat, lng = coords

    return incident_payload(
        id=str(row.get("row_id", "")).strip() or str(row.name),
        text=str(row.get("текст", "")).strip(),
        severity=severity,
        label=severity_label(severity),
        municipality=municipality,
        settlement=settlement or None,
        street=street or None,
        house=house or None,
        address=address_line,
        has_address=has_street_address(row_dict),
        lat=lat,
        lng=lng,
        group=group,
        topic=topic,
        agency=agency,
        agency_email=resolve_agency_email(agency),
        municipality_admin=admin.get("administration"),
        municipality_email=admin.get("email"),
        municipality_phone=admin.get("phone"),
        created_at=str(row.get("дата_создания", "")).strip() or None,
        closed_at=str(row.get("дата_закрытия", "")).strip() or None,
        outcome=str(row.get("итог", "")).strip() or None,
        manually_resolved=bool(row.get("manually_resolved")),
    )


def _filter_by_date_range(
    work: pd.DataFrame,
    *,
    created_from: str | None = None,
    created_to: str | None = None,
) -> pd.DataFrame:
    if not created_from and not created_to:
        return work
    if "дата_создания" not in work.columns:
        return work
    from_dt = _parse_report_date(created_from) if created_from else None
    to_dt = _parse_report_date(created_to) if created_to else None
    if to_dt is not None:
        to_dt = to_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    parsed = work["дата_создания"].map(_parse_report_date)
    mask = parsed.notna()
    if from_dt is not None:
        mask &= parsed >= from_dt
    if to_dt is not None:
        mask &= parsed <= to_dt
    return work[mask]


def _filter_incidents_df(
    work: pd.DataFrame,
    *,
    municipality: str | None = None,
    group: str | None = None,
    topic: str | None = None,
    agency: str | None = None,
    has_address: bool | None = None,
    search: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    resolved: bool | None = None,
) -> pd.DataFrame:
    muni_key = str(municipality or "").strip()
    if muni_key and "муниципалитет" in work.columns:
        work = work[work["муниципалитет"].astype(str).str.strip() == muni_key]

    group_key = str(group or "").strip()
    if group_key and "группа" in work.columns:
        work = work[work["группа"].astype(str).str.strip() == group_key]

    topic_key = str(topic or "").strip()
    if topic_key and "тема" in work.columns:
        work = work[work["тема"].astype(str).str.strip() == topic_key]

    agency_key = str(agency or "").strip()
    if agency_key and "группа" in work.columns:
        work = work[work["группа"].astype(str).map(lambda g: resolve_agency(str(g).strip())) == agency_key]

    if has_address and "улица" in work.columns:
        streets = work["улица"].astype(str).str.strip()
        work = work[streets.ne("") & ~streets.str.lower().isin({"nan", "none", "<na>"})]

    query = str(search or "").strip().lower()
    if query:
        mask = pd.Series(False, index=work.index)
        for col in _SEARCH_COLUMNS:
            if col in work.columns:
                mask |= work[col].astype(str).str.lower().str.contains(query, regex=False, na=False)
        work = work[mask]
    work = _filter_by_date_range(work, created_from=created_from, created_to=created_to)
    if resolved is not None:
        mask = work.apply(is_resolved_row, axis=1)
        work = work[mask] if resolved else work[~mask]
    return work


def list_incident_facets(
    task_id: str,
    jobs_dir: Path,
    *,
    severity_min: int = 1,
    severity_max: int = 4,
    municipality: str | None = None,
    group: str | None = None,
    resolved: bool | None = None,
) -> dict:
    """Справочники для фильтров оператора."""
    if has_stored_job(task_id) and has_incidents_in_db(task_id):
        return list_facets_from_db(
            task_id,
            severity_min=severity_min,
            severity_max=severity_max,
            municipality=municipality,
            group=group,
            resolved=resolved,
        )

    df = load_labeled_pool(task_id, jobs_dir)
    work = df.copy()
    work["severity"] = pd.to_numeric(work["severity"], errors="coerce").fillna(0).astype(int)
    work = work[work["severity"].between(severity_min, severity_max)]
    work = _filter_incidents_df(work, municipality=municipality, group=group, resolved=resolved)

    groups = (
        work["группа"].astype(str).str.strip().replace({"nan": "", "None": ""})
        if "группа" in work.columns else pd.Series(dtype=str)
    )
    topics = (
        work["тема"].astype(str).str.strip().replace({"nan": "", "None": ""})
        if "тема" in work.columns else pd.Series(dtype=str)
    )
    municipalities = (
        work["муниципалитет"].astype(str).str.strip().replace({"nan": "", "None": ""})
        if "муниципалитет" in work.columns else pd.Series(dtype=str)
    )

    group_list = sorted({g for g in groups if g}, key=str.casefold)
    topic_list = sorted({t for t in topics if t}, key=str.casefold)
    municipality_list = sorted({m for m in municipalities if m}, key=str.casefold)

    agencies = sorted(
        {resolve_agency(g) for g in groups if g},
        key=str.casefold,
    )

    with_address = 0
    if "улица" in work.columns:
        streets = work["улица"].astype(str).str.strip()
        with_address = int((streets.ne("") & ~streets.str.lower().isin({"nan", "none", "<na>"})).sum())

    return {
        "groups": group_list,
        "topics": topic_list,
        "municipalities": municipality_list,
        "agencies": agencies,
        "with_address": with_address,
        "total": int(len(work)),
    }


def list_task_incidents(
    task_id: str,
    jobs_dir: Path,
    *,
    severity_min: int = 1,
    severity_max: int = 4,
    municipality: str | None = None,
    group: str | None = None,
    topic: str | None = None,
    agency: str | None = None,
    has_address: bool | None = None,
    geocoded_only: bool | None = None,
    search: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    resolved: bool | None = None,
    limit: int = 300,
    offset: int = 0,
    geocode: bool = False,
    geocode_cache: Path | None = None,
    geocode_cache_only: bool = False,
    geocode_max_fresh: int | None = None,
) -> dict:
    """Возвращает проблемные обращения из БД или labeled.parquet."""
    if has_stored_job(task_id) and has_incidents_in_db(task_id):
        return list_incidents_from_db(
            task_id,
            severity_min=severity_min,
            severity_max=severity_max,
            municipality=municipality,
            group=group,
            topic=topic,
            agency=agency,
            has_address=has_address,
            geocoded_only=geocoded_only,
            search=search,
            created_from=created_from,
            created_to=created_to,
            resolved=resolved,
            limit=limit,
            offset=offset,
            geocode=geocode,
            geocode_cache=geocode_cache,
            geocode_cache_only=geocode_cache_only,
            geocode_max_fresh=geocode_max_fresh,
        )

    df = load_labeled_pool(task_id, jobs_dir)
    if "severity" not in df.columns:
        raise ValueError("В данных нет колонки severity")

    work = df.copy()
    work["severity"] = pd.to_numeric(work["severity"], errors="coerce").fillna(0).astype(int)
    work = work[work["severity"].between(severity_min, severity_max)]
    work = _filter_incidents_df(
        work,
        municipality=municipality,
        group=group,
        topic=topic,
        agency=agency,
        has_address=has_address,
        search=search,
        created_from=created_from,
        created_to=created_to,
        resolved=resolved,
    )

    work = work.sort_values(["severity", "дата_создания"], ascending=[False, False], na_position="last")
    total = int(len(work))
    page = work.iloc[offset : offset + limit]

    address_lines = []
    for _, row in page.iterrows():
        row_dict = {
            "муниципалитет": str(row.get("муниципалитет", "")).strip(),
            "населенный_пункт": str(row.get("населенный_пункт", "")).strip(),
            "улица": str(row.get("улица", "")).strip(),
            "дом": str(row.get("дом", "")).strip(),
        }
        line, has_addr = geocode_query_from_row(row_dict)
        if has_addr and line:
            address_lines.append(line)
    shared_cache = get_geocode_many(address_lines) if geocode else None
    cache_dirty = [False]
    fresh_budget = [geocode_max_fresh] if geocode_max_fresh is not None else None

    items = [
        _row_to_incident(
            row,
            geocode=geocode,
            geocode_cache=geocode_cache,
            geocode_cache_only=geocode_cache_only,
            shared_geocode_cache=shared_cache,
            geocode_cache_dirty=cache_dirty,
            geocode_fresh_budget=fresh_budget,
        )
        for _, row in page.iterrows()
    ]

    return {"items": items, "total": total, "offset": offset, "limit": limit}


def list_task_incident_packages(
    task_id: str,
    jobs_dir: Path,
    *,
    severity_min: int = 1,
    severity_max: int = 4,
    municipality: str | None = None,
    group: str | None = None,
    topic: str | None = None,
    agency: str | None = None,
    has_address: bool | None = None,
    search: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    resolved: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Пакеты обращений по ведомствам — сборка на сервере."""
    if has_stored_job(task_id) and has_incidents_in_db(task_id):
        return list_incident_packages_from_db(
            task_id,
            severity_min=severity_min,
            severity_max=severity_max,
            municipality=municipality,
            group=group,
            topic=topic,
            agency=agency,
            has_address=has_address,
            search=search,
            created_from=created_from,
            created_to=created_to,
            resolved=resolved,
            limit=limit,
            offset=offset,
        )

    df = load_labeled_pool(task_id, jobs_dir)
    if "severity" not in df.columns:
        raise ValueError("В данных нет колонки severity")

    work = df.copy()
    work["severity"] = pd.to_numeric(work["severity"], errors="coerce").fillna(0).astype(int)
    work = work[work["severity"].between(severity_min, severity_max)]
    work = _filter_incidents_df(
        work,
        municipality=municipality,
        group=group,
        topic=topic,
        agency=agency,
        has_address=has_address,
        search=search,
        created_from=created_from,
        created_to=created_to,
        resolved=resolved,
    )
    work = work.sort_values(["severity", "дата_создания"], ascending=[False, False], na_position="last")
    total = int(len(work))
    page = work.iloc[offset : offset + limit]
    items = [_row_to_incident(row) for _, row in page.iterrows()]
    packages = build_agency_packages(items)
    return {
        "packages": packages,
        "total": total,
        "offset": offset,
        "limit": limit,
        "loaded": len(items),
    }


def _marker_in_bbox(
    item: dict,
    *,
    min_lat: float | None,
    max_lat: float | None,
    min_lng: float | None,
    max_lng: float | None,
) -> bool:
    lat = item.get("lat")
    lng = item.get("lng")
    if lat is None or lng is None:
        return False
    if min_lat is not None and lat < min_lat:
        return False
    if max_lat is not None and lat > max_lat:
        return False
    if min_lng is not None and lng < min_lng:
        return False
    if max_lng is not None and lng > max_lng:
        return False
    return True


def list_task_map_markers(
    task_id: str,
    jobs_dir: Path,
    *,
    severity_min: int = 0,
    severity_max: int = 4,
    municipality: str | None = None,
    group: str | None = None,
    topic: str | None = None,
    agency: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    resolved: bool | None = None,
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lng: float | None = None,
    max_lng: float | None = None,
    limit: int = 5000,
    offset: int = 0,
) -> dict:
    """Geocoded map markers — lightweight payload for clustering on the frontend."""
    if has_stored_job(task_id) and has_incidents_in_db(task_id):
        return list_map_markers_from_db(
            task_id,
            severity_min=severity_min,
            severity_max=severity_max,
            municipality=municipality,
            group=group,
            topic=topic,
            agency=agency,
            created_from=created_from,
            created_to=created_to,
            resolved=resolved,
            min_lat=min_lat,
            max_lat=max_lat,
            min_lng=min_lng,
            max_lng=max_lng,
            limit=limit,
            offset=offset,
        )

    payload = list_task_incidents(
        task_id,
        jobs_dir,
        severity_min=severity_min,
        severity_max=severity_max,
        municipality=municipality,
        group=group,
        topic=topic,
        agency=agency,
        created_from=created_from,
        created_to=created_to,
        resolved=resolved,
        limit=limit,
        offset=offset,
    )
    items = [
        {
            "id": item["id"],
            "lat": item["lat"],
            "lng": item["lng"],
            "severity": item["severity"],
            "label": item.get("label", ""),
            "municipality": item.get("municipality", ""),
            "address": item.get("address", ""),
            "text": item.get("text", ""),
            "group": item.get("group", ""),
            "topic": item.get("topic", ""),
            "agency": item.get("agency", ""),
            "agency_email": item.get("agency_email"),
            "municipality_admin": item.get("municipality_admin"),
            "municipality_email": item.get("municipality_email"),
            "municipality_phone": item.get("municipality_phone"),
            "created_at": item.get("created_at"),
        }
        for item in payload["items"]
        if _marker_in_bbox(
            item,
            min_lat=min_lat,
            max_lat=max_lat,
            min_lng=min_lng,
            max_lng=max_lng,
        )
    ]
    return {
        "items": items,
        "total": payload["total"],
        "offset": payload["offset"],
        "limit": payload["limit"],
    }
