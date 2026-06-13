"""Запросы к архиву обращений в БД."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import and_, case, delete, exists, func, or_, select, update
from sqlalchemy.orm import Session

from app.address import geocode_query_from_row, has_street_address
from app.constants import CITIZEN_ROW_PREFIX, LIVE_STREAM_TASK_ID
from app.incidents import incident_payload
from app.db.models import GeocodeCacheEntry, IncidentRegistry, StoredIncident, StoredJob
from app.db.session import get_session
from app.db.geocode_cache_repo import get_geocode_many
from app.geocode import geocode_address
from app.report import severity_label
from app.resolved import is_resolved_outcome


def _parse_iso_ts(value: str | None) -> datetime | None:
    """Parse ISO timestamps from JS (…Z) or Python (+00:00) for reliable comparison."""
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utc_iso_z() -> str:
    """UTC timestamp compatible with JS Date.toISOString() (lexicographic order)."""
    dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def has_stored_job(task_id: str) -> bool:
    with get_session() as session:
        return session.get(StoredJob, task_id) is not None


def get_stored_report(task_id: str) -> dict | None:
    with get_session() as session:
        job = session.get(StoredJob, task_id)
        if job is None or not job.report_json:
            return None
        try:
            return json.loads(job.report_json)
        except json.JSONDecodeError:
            return None


def list_stored_jobs() -> list[dict]:
    with get_session() as session:
        rows = session.scalars(
            select(StoredJob).order_by(StoredJob.stored_at.desc())
        ).all()
        return [_stored_job_dict(row) for row in rows]


def _stored_job_dict(row: StoredJob) -> dict:
    return {
        "task_id": row.task_id,
        "filename": row.filename,
        "created_at": row.created_at,
        "stored_at": row.stored_at,
        "rows_total": row.rows_total,
        "problem_count": row.problem_count,
        "municipality_count": row.municipality_count,
        "incident_count": row.incident_count,
        "content_hash": row.content_hash,
        "is_duplicate": bool(row.is_duplicate),
        "duplicate_of_task_id": row.duplicate_of_task_id,
    }


def find_canonical_job_by_hash(
    session: Session,
    content_hash: str | None,
    *,
    exclude_task_id: str | None = None,
) -> StoredJob | None:
    """Первая (каноническая) задача с тем же хэшем файла и импортированными обращениями."""
    if not content_hash:
        return None
    stmt = (
        select(StoredJob)
        .where(
            StoredJob.content_hash == content_hash,
            StoredJob.is_duplicate.is_(False),
            StoredJob.incident_count > 0,
        )
        .order_by(StoredJob.stored_at.asc())
        .limit(1)
    )
    if exclude_task_id:
        stmt = stmt.where(StoredJob.task_id != exclude_task_id)
    return session.scalar(stmt)


def _content_hash_from_disk(task_id: str) -> str | None:
    from app.config import paths
    from app.file_fingerprint import find_job_input_file, sha256_file

    job_dir = paths.JOBS_DIR / task_id
    input_path = find_job_input_file(job_dir)
    if input_path is not None:
        try:
            return sha256_file(input_path)
        except OSError:
            pass
    parquet_path = job_dir / "cache" / "labeled.parquet"
    if parquet_path.is_file():
        try:
            return sha256_file(parquet_path)
        except OSError:
            return None
    return None


def backfill_stored_job_hashes(session: Session) -> int:
    """Заполняет content_hash у старых задач из input-файла в cache."""
    rows = session.scalars(
        select(StoredJob).where(
            StoredJob.content_hash.is_(None),
            StoredJob.task_id != LIVE_STREAM_TASK_ID,
        )
    ).all()
    updated = 0
    for job in rows:
        content_hash = _content_hash_from_disk(job.task_id)
        if content_hash:
            job.content_hash = content_hash
            updated += 1
    if updated:
        session.flush()
    return updated


def find_canonical_job_for_upload(
    session: Session,
    content_hash: str | None,
    *,
    exclude_task_id: str | None = None,
) -> StoredJob | None:
    """Ищет оригинал по хэшу, предварительно восстанавливая хэши старых загрузок."""
    if not content_hash:
        return None
    canonical = find_canonical_job_by_hash(session, content_hash, exclude_task_id=exclude_task_id)
    if canonical is not None:
        return canonical
    backfill_stored_job_hashes(session)
    return find_canonical_job_by_hash(session, content_hash, exclude_task_id=exclude_task_id)


def demote_stored_job_to_duplicate(
    session: Session,
    task_id: str,
    duplicate_of_task_id: str,
) -> None:
    """Переводит ранее импортированную задачу в дубликат и удаляет её обращения из БД."""
    job = session.get(StoredJob, task_id)
    if job is None or job.is_duplicate or job.task_id == LIVE_STREAM_TASK_ID:
        return
    if not job.content_hash:
        job.content_hash = _content_hash_from_disk(task_id)
    session.execute(
        delete(StoredIncident).where(
            StoredIncident.task_id == task_id,
            ~StoredIncident.row_id.like(f"{CITIZEN_ROW_PREFIX}%"),
        )
    )
    job.is_duplicate = True
    job.duplicate_of_task_id = duplicate_of_task_id
    job.incident_count = int(
        session.scalar(
            select(func.count())
            .select_from(StoredIncident)
            .where(StoredIncident.task_id == task_id)
        )
        or 0
    )
    session.flush()


def reconcile_duplicate_stored_jobs() -> dict:
    """
    Backfill хэшей и схлопывание уже импортированных дубликатов.
    Оставляет самую раннюю задау с данными, остальные помечает как дубликаты.
    """
    with get_session() as session:
        backfilled = backfill_stored_job_hashes(session)
        rows = session.scalars(
            select(StoredJob).where(
                StoredJob.is_duplicate.is_(False),
                StoredJob.incident_count > 0,
                StoredJob.content_hash.isnot(None),
                StoredJob.task_id != LIVE_STREAM_TASK_ID,
            ).order_by(StoredJob.stored_at.asc())
        ).all()
        by_hash: dict[str, list[StoredJob]] = {}
        for job in rows:
            by_hash.setdefault(job.content_hash or "", []).append(job)

        demoted: list[str] = []
        for content_hash, group in by_hash.items():
            if not content_hash or len(group) < 2:
                continue
            canonical = group[0]
            for dup in group[1:]:
                demote_stored_job_to_duplicate(session, dup.task_id, canonical.task_id)
                demoted.append(dup.task_id)
        return {"backfilled": backfilled, "demoted": demoted}


def canonical_content_hashes() -> set[str]:
    with get_session() as session:
        rows = session.scalars(
            select(StoredJob.content_hash).where(
                StoredJob.content_hash.isnot(None),
                StoredJob.is_duplicate.is_(False),
                StoredJob.incident_count > 0,
            )
        ).all()
        return {h for h in rows if h}


def delete_stored_job(task_id: str) -> bool:
    with get_session() as session:
        job = session.get(StoredJob, task_id)
        if job is None:
            return False
        session.delete(job)
        return True


def _incident_to_api(
    row: StoredIncident,
    *,
    geocode: bool = False,
    geocode_cache=None,
    geocode_cache_only: bool = False,
    shared_geocode_cache: dict | None = None,
    geocode_cache_dirty: list[bool] | None = None,
    geocode_fresh_budget: list[int] | None = None,
) -> dict:
    lat, lng = row.lat, row.lng
    if geocode and row.has_address and geocode_cache is not None and lat is None:
        coords = geocode_address(
            row.address_line,
            geocode_cache,
            cache_only=geocode_cache_only,
            cache=shared_geocode_cache,
            cache_dirty=geocode_cache_dirty,
            fresh_budget=geocode_fresh_budget,
        )
        if coords:
            lat, lng = coords
            row.lat = lat
            row.lng = lng

    return incident_payload(
        id=row.row_id or str(row.id),
        text=row.text,
        severity=int(row.severity),
        label=severity_label(row.severity),
        municipality=row.municipality or "",
        settlement=row.settlement,
        street=row.street,
        house=row.house,
        address=row.address_line or "",
        has_address=bool(row.has_address),
        lat=lat,
        lng=lng,
        group=row.group_name or "",
        topic=row.topic or "",
        agency=row.agency or "",
        agency_email=row.agency_email,
        municipality_admin=row.municipality_admin,
        municipality_email=row.municipality_email,
        municipality_phone=row.municipality_phone,
        created_at=row.created_at,
        incident_number=row.incident_number,
        closed_at=row.closed_at,
        workflow_step=row.workflow_step,
        outcome=row.outcome,
        manually_resolved=bool(row.manually_resolved),
        resolved_at=row.resolved_at,
        resolved_note=row.resolved_note,
    )


def _created_date_key_expr():
    """Нормализует created_at (ISO, DD.MM.YYYY, …) в YYYY-MM-DD для сравнения."""
    col = StoredIncident.created_at
    dmy = func.concat(
        func.substr(col, 7, 4),
        "-",
        func.substr(col, 4, 2),
        "-",
        func.substr(col, 1, 2),
    )
    return case(
        (col.like("____-__-__%"), func.substr(col, 1, 10)),
        (col.like("__.__.____%"), dmy),
        else_=func.substr(col, 1, 10),
    )


def _outcome_resolved_sql_expr():
    """Итог (AD): решено, разъяснено, перенаправлено."""
    col = func.lower(func.trim(func.coalesce(StoredIncident.outcome, "")))
    return and_(
        col != "",
        col.notin_(("nan", "none", "<na>")),
        or_(
            col.in_(("решено", "разъяснено", "перенаправлено")),
            col.like("решено%"),
            col.like("разъяснено%"),
            col.like("перенаправлено%"),
        ),
    )


def _registry_resolved_expr():
    """Решено через IncidentRegistry по внешнему ID (как в load_forecast_dataframe)."""
    inc = func.trim(func.coalesce(StoredIncident.incident_number, ""))
    rid = func.trim(func.coalesce(StoredIncident.row_id, ""))
    prefix = CITIZEN_ROW_PREFIX
    return or_(
        and_(
            inc != "",
            exists(
                select(1).where(
                    IncidentRegistry.external_id == inc,
                    IncidentRegistry.manually_resolved.is_(True),
                )
            ),
        ),
        and_(
            rid != "",
            ~rid.like(f"{prefix}%"),
            ~rid.like("no:%"),
            func.length(rid) >= 5,
            exists(
                select(1).where(
                    IncidentRegistry.external_id == rid,
                    IncidentRegistry.manually_resolved.is_(True),
                )
            ),
        ),
    )


def _compute_is_resolved(
    *,
    manually_resolved: bool,
    outcome: str | None,
    registry_resolved: bool = False,
) -> bool:
    if manually_resolved or registry_resolved:
        return True
    return is_resolved_outcome(outcome)


def _sync_row_is_resolved(row: StoredIncident) -> None:
    row.is_resolved = _compute_is_resolved(
        manually_resolved=bool(row.manually_resolved),
        outcome=row.outcome,
    )


def _propagate_registry_resolved_flag(session: Session, external_id: str, resolved: bool) -> None:
    """Синхронизирует is_resolved по всем задачам при изменении реестра."""
    if not external_id:
        return
    prefix = CITIZEN_ROW_PREFIX
    match_clause = or_(
        StoredIncident.incident_number == external_id,
        and_(
            StoredIncident.row_id == external_id,
            StoredIncident.row_id != "",
            ~StoredIncident.row_id.like(f"{prefix}%"),
            ~StoredIncident.row_id.like("no:%"),
        ),
    )
    if resolved:
        session.execute(
            update(StoredIncident).where(match_clause).values(is_resolved=True)
        )
        return
    rows = session.scalars(select(StoredIncident).where(match_clause)).all()
    for row in rows:
        _sync_row_is_resolved(row)


def backfill_is_resolved_column(eng) -> None:
    """Заполняет is_resolved для существующих строк (один раз при миграции)."""
    from sqlalchemy import inspect

    inspector = inspect(eng)
    if "stored_incidents" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("stored_incidents")}
    if "is_resolved" not in cols:
        return

    chunk = 2000
    with get_session() as session:
        resolved_ids = set(
            session.scalars(
                select(IncidentRegistry.external_id).where(
                    IncidentRegistry.manually_resolved.is_(True)
                )
            ).all()
        )
        last_id = 0
        while True:
            rows = session.scalars(
                select(StoredIncident)
                .where(StoredIncident.id > last_id)
                .order_by(StoredIncident.id)
                .limit(chunk)
            ).all()
            if not rows:
                break
            for row in rows:
                ext = _registry_external_id(row.row_id, row.incident_number or "")
                row.is_resolved = _compute_is_resolved(
                    manually_resolved=bool(row.manually_resolved),
                    outcome=row.outcome,
                    registry_resolved=bool(ext and ext in resolved_ids),
                )
                last_id = row.id
            session.flush()


def _is_resolved_sql_expr():
    """Совпадает с app.resolved.is_resolved_row + реестр внешних ID."""
    return or_(
        StoredIncident.manually_resolved.is_(True),
        _outcome_resolved_sql_expr(),
        _registry_resolved_expr(),
    )


def _apply_filters(
    query,
    *,
    severity_min,
    severity_max,
    municipality,
    group,
    topic,
    agency,
    has_address,
    geocoded_only=None,
    search,
    created_from=None,
    created_to=None,
    resolved=None,
):
    query = query.where(StoredIncident.severity.between(severity_min, severity_max))
    if municipality:
        query = query.where(StoredIncident.municipality == municipality.strip())
    if group:
        query = query.where(StoredIncident.group_name == group.strip())
    if topic:
        query = query.where(StoredIncident.topic == topic.strip())
    if agency:
        query = query.where(StoredIncident.agency == agency.strip())
    if has_address:
        query = query.where(StoredIncident.has_address.is_(True))
    if geocoded_only is True:
        query = query.where(StoredIncident.lat.is_not(None), StoredIncident.lng.is_not(None))
    elif geocoded_only is False:
        query = query.where(StoredIncident.lat.is_(None))
    if search:
        like = f"%{search.strip().lower()}%"
        query = query.where(
            func.lower(StoredIncident.text).like(like)
            | func.lower(StoredIncident.topic).like(like)
            | func.lower(StoredIncident.street).like(like)
            | func.lower(StoredIncident.municipality).like(like)
            | func.lower(StoredIncident.group_name).like(like)
        )
    date_key = _created_date_key_expr()
    from_key = str(created_from or "").strip()[:10]
    to_key = str(created_to or "").strip()[:10]
    if from_key:
        query = query.where(date_key >= from_key)
    if to_key:
        query = query.where(date_key <= to_key)
    if resolved is True:
        query = query.where(StoredIncident.is_resolved.is_(True))
    elif resolved is False:
        query = query.where(StoredIncident.is_resolved.is_(False))
    return query


def _apply_bbox_filter(
    query,
    *,
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lng: float | None = None,
    max_lng: float | None = None,
):
    if min_lat is not None:
        query = query.where(StoredIncident.lat >= min_lat)
    if max_lat is not None:
        query = query.where(StoredIncident.lat <= max_lat)
    if min_lng is not None:
        query = query.where(StoredIncident.lng >= min_lng)
    if max_lng is not None:
        query = query.where(StoredIncident.lng <= max_lng)
    return query


def _facet_where_clauses(
    task_id: str,
    *,
    severity_min: int,
    severity_max: int,
    municipality: str | None = None,
    group: str | None = None,
    resolved: bool | None = None,
):
    clauses = [
        StoredIncident.task_id == task_id,
        StoredIncident.severity.between(severity_min, severity_max),
    ]
    if municipality:
        clauses.append(StoredIncident.municipality == municipality.strip())
    if group:
        clauses.append(StoredIncident.group_name == group.strip())
    if resolved is True:
        clauses.append(StoredIncident.is_resolved.is_(True))
    elif resolved is False:
        clauses.append(StoredIncident.is_resolved.is_(False))
    return clauses


def _distinct_text_values(session: Session, column, where_clauses) -> list[str]:
    rows = session.scalars(
        select(column)
        .where(*where_clauses)
        .where(column.is_not(None))
        .where(column != "")
        .distinct()
        .order_by(column)
    ).all()
    return sorted({str(v).strip() for v in rows if str(v).strip()}, key=str.casefold)


def list_incidents_from_db(
    task_id: str,
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
    geocode_cache=None,
    geocode_cache_only: bool = False,
    geocode_max_fresh: int | None = None,
) -> dict:
    with get_session() as session:
        base = select(StoredIncident).where(StoredIncident.task_id == task_id)
        base = _apply_filters(
            base,
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
        )
        full_total = func.count().over().label("full_total")
        page_stmt = (
            base.add_columns(full_total)
            .order_by(StoredIncident.severity.desc(), StoredIncident.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        page_rows = session.execute(page_stmt).all()
        if page_rows:
            rows = [row[0] for row in page_rows]
            total = int(page_rows[0][1])
        else:
            rows = []
            if offset == 0:
                total = 0
            else:
                count_q = select(func.count()).select_from(StoredIncident).where(
                    StoredIncident.task_id == task_id
                )
                count_q = _apply_filters(
                    count_q,
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
                )
                total = int(session.scalar(count_q) or 0)

        shared_cache = (
            get_geocode_many([row.address_line for row in rows if row.has_address and row.lat is None and row.address_line])
            if geocode
            else None
        )
        cache_dirty = [False]
        fresh_budget = [geocode_max_fresh] if geocode_max_fresh is not None else None

        items = [
            _incident_to_api(
                row,
                geocode=geocode,
                geocode_cache=geocode_cache,
                geocode_cache_only=geocode_cache_only,
                shared_geocode_cache=shared_cache,
                geocode_cache_dirty=cache_dirty,
                geocode_fresh_budget=fresh_budget,
            )
            for row in rows
        ]

        return {"items": items, "total": int(total), "offset": offset, "limit": limit}


def list_incident_packages_from_db(
    task_id: str,
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
    """Страница обращений → пакеты на сервере (быстрая первая порция)."""
    from app.incident_packages import build_agency_packages

    with get_session() as session:
        base = select(StoredIncident).where(StoredIncident.task_id == task_id)
        base = _apply_filters(
            base,
            severity_min=severity_min,
            severity_max=severity_max,
            municipality=municipality,
            group=group,
            topic=topic,
            agency=agency,
            has_address=has_address,
            geocoded_only=None,
            search=search,
            created_from=created_from,
            created_to=created_to,
            resolved=resolved,
        )
        full_total = func.count().over().label("full_total")
        page_stmt = (
            base.add_columns(full_total)
            .order_by(StoredIncident.severity.desc(), StoredIncident.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        page_rows = session.execute(page_stmt).all()
        if page_rows:
            rows = [row[0] for row in page_rows]
            total = int(page_rows[0][1])
        else:
            rows = []
            if offset == 0:
                total = 0
            else:
                count_q = select(func.count()).select_from(StoredIncident).where(
                    StoredIncident.task_id == task_id
                )
                count_q = _apply_filters(
                    count_q,
                    severity_min=severity_min,
                    severity_max=severity_max,
                    municipality=municipality,
                    group=group,
                    topic=topic,
                    agency=agency,
                    has_address=has_address,
                    geocoded_only=None,
                    search=search,
                    created_from=created_from,
                    created_to=created_to,
                    resolved=resolved,
                )
                total = int(session.scalar(count_q) or 0)

        items = [_incident_to_api(row) for row in rows]
        packages = build_agency_packages(items)
        return {
            "packages": packages,
            "total": int(total),
            "offset": offset,
            "limit": limit,
            "loaded": len(items),
        }


def _map_marker_from_row(row: StoredIncident) -> dict:
    return {
        "id": row.row_id or str(row.id),
        "lat": float(row.lat),
        "lng": float(row.lng),
        "severity": int(row.severity),
        "label": severity_label(row.severity),
        "municipality": row.municipality or "",
        "address": row.address_line or "",
        "text": row.text or "",
        "group": row.group_name or "",
        "topic": row.topic or "",
        "agency": row.agency or "",
        "agency_email": row.agency_email,
        "municipality_admin": row.municipality_admin,
        "municipality_email": row.municipality_email,
        "municipality_phone": row.municipality_phone,
        "created_at": row.created_at,
        "closed_at": row.closed_at,
        "outcome": row.outcome,
        "manually_resolved": bool(row.manually_resolved),
    }


def list_map_markers_from_db(
    task_id: str,
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
    """Lightweight geocoded incidents for map markers (lat/lng + popup fields only)."""
    with get_session() as session:
        base = select(StoredIncident).where(
            StoredIncident.task_id == task_id,
            StoredIncident.lat.is_not(None),
            StoredIncident.lng.is_not(None),
        )
        base = _apply_filters(
            base,
            severity_min=severity_min,
            severity_max=severity_max,
            municipality=municipality,
            group=group,
            topic=topic,
            agency=agency,
            has_address=None,
            geocoded_only=None,
            search=None,
            created_from=created_from,
            created_to=created_to,
            resolved=resolved,
        )
        base = _apply_bbox_filter(
            base,
            min_lat=min_lat,
            max_lat=max_lat,
            min_lng=min_lng,
            max_lng=max_lng,
        )
        count_q = select(func.count()).select_from(StoredIncident).where(
            StoredIncident.task_id == task_id,
            StoredIncident.lat.is_not(None),
            StoredIncident.lng.is_not(None),
        )
        count_q = _apply_filters(
            count_q,
            severity_min=severity_min,
            severity_max=severity_max,
            municipality=municipality,
            group=group,
            topic=topic,
            agency=agency,
            has_address=None,
            geocoded_only=None,
            search=None,
            created_from=created_from,
            created_to=created_to,
            resolved=resolved,
        )
        count_q = _apply_bbox_filter(
            count_q,
            min_lat=min_lat,
            max_lat=max_lat,
            min_lng=min_lng,
            max_lng=max_lng,
        )
        total = session.scalar(count_q) or 0
        rows = session.scalars(
            base.order_by(StoredIncident.severity.desc(), StoredIncident.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        items = [_map_marker_from_row(row) for row in rows]
        return {"items": items, "total": int(total), "offset": offset, "limit": limit}


def list_facets_from_db(
    task_id: str,
    *,
    severity_min: int = 1,
    severity_max: int = 4,
    municipality: str | None = None,
    group: str | None = None,
    resolved: bool | None = None,
) -> dict:
    with get_session() as session:
        where = _facet_where_clauses(
            task_id,
            severity_min=severity_min,
            severity_max=severity_max,
            municipality=municipality,
            group=group,
            resolved=resolved,
        )
        groups = _distinct_text_values(session, StoredIncident.group_name, where)
        topics = _distinct_text_values(session, StoredIncident.topic, where)
        municipalities = _distinct_text_values(session, StoredIncident.municipality, where)
        agencies = _distinct_text_values(session, StoredIncident.agency, where)
        with_address = session.scalar(
            select(func.count())
            .select_from(StoredIncident)
            .where(*where, StoredIncident.has_address.is_(True))
        ) or 0
        total = session.scalar(
            select(func.count()).select_from(StoredIncident).where(*where)
        ) or 0

        return {
            "groups": groups,
            "topics": topics,
            "municipalities": municipalities,
            "agencies": agencies,
            "with_address": int(with_address),
            "total": int(total),
        }


def count_canonical_archive_jobs() -> int:
    """Число файловых загрузок в архиве — как раздел «В базе» (без live и дубликатов)."""
    with get_session() as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(StoredJob)
                .where(
                    StoredJob.is_duplicate.is_(False),
                    StoredJob.task_id != LIVE_STREAM_TASK_ID,
                )
            )
            or 0
        )


def load_forecast_dataframe():
    """Все проблемные обращения из БД для прогноза (решённые и нерешённые; дедуп по ID)."""
    import pandas as pd

    from app.report_dates import DATE_COLUMN

    with get_session() as session:
        rows = session.scalars(
            select(StoredIncident).where(
                StoredIncident.is_problem.is_(True),
                StoredIncident.created_at.isnot(None),
                StoredIncident.created_at != "",
            )
        ).all()
        jobs_count = int(
            session.scalar(
                select(func.count())
                .select_from(StoredJob)
                .where(
                    StoredJob.is_duplicate.is_(False),
                    StoredJob.task_id != LIVE_STREAM_TASK_ID,
                )
            )
            or 0
        )
        last_stored_at = session.scalar(
            select(func.max(StoredJob.stored_at)).where(
                StoredJob.is_duplicate.is_(False),
                StoredJob.task_id != LIVE_STREAM_TASK_ID,
            )
        ) or ""

        records: list[dict] = []
        for row in rows:
            ext = _registry_external_id(row.row_id, row.incident_number or "")
            dedupe_key = ext or f"{row.task_id}:{row.row_id}"
            records.append(
                {
                    "_dedupe_key": dedupe_key,
                    "_id": row.id,
                    DATE_COLUMN: row.created_at,
                    "closed_at": row.closed_at,
                    "муниципалитет": row.municipality or "",
                    "тема": row.topic or "",
                    "группа": row.group_name or "",
                    "ведомство": row.agency or "",
                    "severity": int(row.severity or 0),
                    "is_problem": True,
                    "has_address": bool(row.has_address),
                    "is_geocoded": row.lat is not None and row.lng is not None,
                }
            )

    if not records:
        return pd.DataFrame(), int(jobs_count), str(last_stored_at)

    df = pd.DataFrame(records)
    df["_sort_closed"] = pd.to_datetime(df["closed_at"], errors="coerce")
    df["_sort_created"] = pd.to_datetime(df[DATE_COLUMN], errors="coerce")
    df = df.sort_values(
        ["_sort_closed", "_sort_created", "_id"],
        ascending=[False, False, False],
        na_position="last",
    )
    df = df.drop_duplicates(subset=["_dedupe_key"], keep="first")
    df = df.drop(columns=["_dedupe_key", "_id", "_sort_closed", "_sort_created"])
    return df.reset_index(drop=True), int(jobs_count), str(last_stored_at)


def list_global_facets_from_db(
    *,
    severity_min: int = 0,
    severity_max: int = 4,
) -> dict:
    """Справочники групп/тем/МО по всем обращениям в Postgres."""
    with get_session() as session:
        where = [StoredIncident.severity.between(severity_min, severity_max)]
        groups = _distinct_text_values(session, StoredIncident.group_name, where)
        topics = _distinct_text_values(session, StoredIncident.topic, where)
        municipalities = _distinct_text_values(session, StoredIncident.municipality, where)
        agencies = _distinct_text_values(session, StoredIncident.agency, where)
        with_address = session.scalar(
            select(func.count())
            .select_from(StoredIncident)
            .where(*where, StoredIncident.has_address.is_(True))
        ) or 0
        total = session.scalar(
            select(func.count()).select_from(StoredIncident).where(*where)
        ) or 0

        return {
            "groups": groups,
            "topics": topics,
            "municipalities": municipalities,
            "agencies": agencies,
            "with_address": int(with_address),
            "total": int(total),
        }


def resolve_default_task_id() -> str | None:
    """Последняя задача в БД с данными (кроме служебного live-потока)."""
    for row in list_stored_jobs():
        tid = row["task_id"]
        if tid == LIVE_STREAM_TASK_ID:
            continue
        if row.get("is_duplicate"):
            continue
        if row.get("incident_count", 0) > 0:
            return tid
        if get_stored_report(tid):
            return tid
    return None


def has_bulk_incidents_in_db(task_id: str) -> bool:
    """Есть ли в БД импортированные строки (не только citizen-*)."""
    with get_session() as session:
        count = session.scalar(
            select(func.count())
            .select_from(StoredIncident)
            .where(
                StoredIncident.task_id == task_id,
                ~StoredIncident.row_id.like(f"{CITIZEN_ROW_PREFIX}%"),
            )
        )
        return int(count or 0) > 0


def has_incidents_in_db(task_id: str) -> bool:
    """Есть ли любые обращения задачи в Postgres (включая citizen-*)."""
    with get_session() as session:
        count = session.scalar(
            select(func.count())
            .select_from(StoredIncident)
            .where(StoredIncident.task_id == task_id)
        )
        return int(count or 0) > 0


def register_stored_job(
    session: Session,
    *,
    task_id: str,
    filename: str,
    created_at: str,
    rows_total: int,
    problem_count: int | None,
    municipality_count: int | None,
    report: dict | None = None,
    content_hash: str | None = None,
    is_duplicate: bool = False,
    duplicate_of_task_id: str | None = None,
) -> None:
    if session.get(StoredJob, task_id) is not None:
        return
    session.add(
        StoredJob(
            task_id=task_id,
            filename=filename,
            created_at=created_at,
            rows_total=rows_total,
            problem_count=problem_count,
            municipality_count=municipality_count,
            report_json=json.dumps(report or {}, ensure_ascii=False),
            stored_at=datetime.now(timezone.utc).isoformat(),
            incident_count=0,
            content_hash=content_hash,
            is_duplicate=is_duplicate,
            duplicate_of_task_id=duplicate_of_task_id,
        )
    )
    session.flush()


def register_duplicate_stored_job(
    session: Session,
    *,
    task_id: str,
    filename: str,
    created_at: str,
    rows_total: int,
    problem_count: int | None,
    municipality_count: int | None,
    report: dict,
    content_hash: str,
    duplicate_of_task_id: str,
) -> None:
    """Метаданные повторной загрузки без записи обращений в БД."""
    existing = session.get(StoredJob, task_id)
    if existing:
        session.execute(
            delete(StoredIncident).where(
                StoredIncident.task_id == task_id,
                ~StoredIncident.row_id.like(f"{CITIZEN_ROW_PREFIX}%"),
            )
        )
        session.delete(existing)
        session.flush()

    session.add(
        StoredJob(
            task_id=task_id,
            filename=filename,
            created_at=created_at,
            rows_total=rows_total,
            problem_count=problem_count,
            municipality_count=municipality_count,
            report_json=json.dumps(report, ensure_ascii=False),
            stored_at=datetime.now(timezone.utc).isoformat(),
            incident_count=0,
            content_hash=content_hash,
            is_duplicate=True,
            duplicate_of_task_id=duplicate_of_task_id,
        )
    )
    session.flush()


def insert_citizen_complaint_row(incident: dict) -> None:
    with get_session() as session:
        job = session.get(StoredJob, incident["task_id"])
        if job is None:
            raise ValueError("Задача не найдена в базе. Дождитесь завершения анализа или импортируйте в архив.")
        session.add(StoredIncident(**incident))
        session.flush()
        job.incident_count = int(
            session.scalar(
                select(func.count())
                .select_from(StoredIncident)
                .where(StoredIncident.task_id == incident["task_id"])
            )
            or 0
        )
        if incident.get("is_problem"):
            job.problem_count = int(job.problem_count or 0) + 1
        job.rows_total = int(job.rows_total or 0) + 1


def delete_citizen_incident(task_id: str, row_id: str) -> bool:
    if not str(row_id).startswith(CITIZEN_ROW_PREFIX):
        raise ValueError("Можно удалять только обращения граждан (live-поток)")
    with get_session() as session:
        row = session.scalar(
            select(StoredIncident).where(
                StoredIncident.task_id == task_id,
                StoredIncident.row_id == row_id,
            )
        )
        if row is None:
            return False
        was_problem = bool(row.is_problem)
        session.delete(row)
        session.flush()
        job = session.get(StoredJob, task_id)
        if job is not None:
            job.incident_count = max(0, int(job.incident_count or 0) - 1)
            job.rows_total = max(0, int(job.rows_total or 0) - 1)
            if was_problem:
                job.problem_count = max(0, int(job.problem_count or 0) - 1)
        return True


def geocode_and_save_incident(
    task_id: str,
    row_id: str,
    *,
    geocode_cache,
    cache_only: bool = False,
) -> dict:
    """Геокодирует обращение через Nominatim, сохраняет lat/lng в Postgres и файловый кэш."""
    with get_session() as session:
        row = session.scalar(
            select(StoredIncident).where(
                StoredIncident.task_id == task_id,
                StoredIncident.row_id == row_id,
            )
        )
        if row is None:
            raise FileNotFoundError("Обращение не найдено в базе")
        if not row.has_address or not row.address_line:
            raise ValueError("У обращения нет адреса для геокодирования")
        if row.lat is not None and row.lng is not None and cache_only:
            session.expunge(row)
            return _incident_to_api(row)
        coords = geocode_address(
            row.address_line,
            geocode_cache,
            cache_only=cache_only,
            force_fresh=not cache_only,
        )
        if not coords:
            raise ValueError(
                "Координаты не найдены"
                + (" (только кэш)" if cache_only else " — Nominatim не вернул результат")
            )
        row.lat, row.lng = coords
        session.flush()
        session.expunge(row)
        return _incident_to_api(row)


geocode_and_save_citizen_incident = geocode_and_save_incident


def list_recent_citizen_complaints(
    task_id: str | None = None,
    *,
    since: str | None = None,
    limit: int = 20,
) -> list[StoredIncident]:
    since_dt = _parse_iso_ts(since) if since else None
    since_iso = (
        since_dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{since_dt.microsecond // 1000:03d}Z"
        if since_dt
        else None
    )
    cap = min(max(limit, 1), 100)
    with get_session() as session:
        filters = [StoredIncident.row_id.like(f"{CITIZEN_ROW_PREFIX}%")]
        if task_id:
            filters.append(StoredIncident.task_id == task_id)
        if since_iso:
            filters.append(StoredIncident.created_at > since_iso)
        q = (
            select(StoredIncident)
            .where(*filters)
            .order_by(StoredIncident.id.desc())
            .limit(cap)
        )
        rows = list(session.scalars(q).all())
        for row in rows:
            session.expunge(row)
        return rows


def _pending_geocode_filters(task_id: str):
    """Адреса без координат, исключая уже провалившиеся в geocode_cache."""
    failed_keys = select(GeocodeCacheEntry.address_key).where(GeocodeCacheEntry.failed.is_(True))
    address_key = func.lower(func.trim(StoredIncident.address_line))
    return (
        StoredIncident.task_id == task_id,
        StoredIncident.has_address.is_(True),
        StoredIncident.address_line != "",
        StoredIncident.lat.is_(None),
        ~address_key.in_(failed_keys),
    )


def fetch_pending_address_lines(task_id: str, *, limit: int = 40) -> list[str]:
    with get_session() as session:
        rows = session.scalars(
            select(StoredIncident.address_line)
            .where(*_pending_geocode_filters(task_id))
            .distinct()
            .limit(limit)
        ).all()
        return [str(r).strip() for r in rows if str(r).strip()]


def apply_geocode_to_address(task_id: str, address_line: str, lat: float, lng: float) -> int:
    with get_session() as session:
        result = session.execute(
            update(StoredIncident)
            .where(
                StoredIncident.task_id == task_id,
                StoredIncident.address_line == address_line,
                StoredIncident.lat.is_(None),
            )
            .values(lat=lat, lng=lng)
        )
        return int(result.rowcount or 0)


def count_geocode_stats(task_id: str) -> dict:
    with get_session() as session:
        total_addresses = session.scalar(
            select(func.count(func.distinct(StoredIncident.address_line))).where(
                StoredIncident.task_id == task_id,
                StoredIncident.has_address.is_(True),
                StoredIncident.address_line != "",
            )
        ) or 0
        pending_addresses = session.scalar(
            select(func.count(func.distinct(StoredIncident.address_line))).where(
                *_pending_geocode_filters(task_id)
            )
        ) or 0
        geocoded_incidents = session.scalar(
            select(func.count())
            .select_from(StoredIncident)
            .where(
                StoredIncident.task_id == task_id,
                StoredIncident.has_address.is_(True),
                StoredIncident.lat.is_not(None),
                StoredIncident.lng.is_not(None),
            )
        ) or 0
        return {
            "total_addresses": int(total_addresses),
            "pending_addresses": int(pending_addresses),
            "geocoded_incidents": int(geocoded_incidents),
        }


def upsert_job_and_incidents(
    session: Session,
    *,
    task_id: str,
    filename: str,
    created_at: str,
    rows_total: int,
    problem_count: int | None,
    municipality_count: int | None,
    report: dict,
    incidents: list[dict],
    content_hash: str | None = None,
) -> None:
    session.execute(
        delete(StoredIncident).where(
            StoredIncident.task_id == task_id,
            ~StoredIncident.row_id.like(f"{CITIZEN_ROW_PREFIX}%"),
        )
    )
    existing = session.get(StoredJob, task_id)
    if existing:
        session.delete(existing)
        session.flush()

    job = StoredJob(
        task_id=task_id,
        filename=filename,
        created_at=created_at,
        rows_total=rows_total,
        problem_count=problem_count,
        municipality_count=municipality_count,
        report_json=json.dumps(report, ensure_ascii=False),
        stored_at=datetime.now(timezone.utc).isoformat(),
        incident_count=len(incidents),
        content_hash=content_hash,
        is_duplicate=False,
        duplicate_of_task_id=None,
    )
    session.add(job)
    session.flush()

    chunk = 500
    for i in range(0, len(incidents), chunk):
        session.add_all([StoredIncident(**item) for item in incidents[i : i + chunk]])
        session.flush()
    total = session.scalar(
        select(func.count()).select_from(StoredIncident).where(StoredIncident.task_id == task_id)
    )
    job.incident_count = int(total or 0)
    sync_incident_registry(session, task_id, incidents)


def _registry_external_id(row_id: str, id_обращения: str) -> str | None:
    ext = str(id_обращения or "").strip()
    if ext:
        return ext
    rid = str(row_id or "").strip()
    if rid.startswith(CITIZEN_ROW_PREFIX) or rid.startswith("no:"):
        return None
    if rid.isdigit() and len(rid) >= 5:
        return rid
    return None


REGISTRY_IN_CHUNK = 5000


def _lookup_incident_registry(
    session: Session,
    external_ids: list[str],
    *,
    resolved_only: bool = False,
) -> dict[str, IncidentRegistry]:
    """Пакетная выборка из incident_registry (лимит psycopg — 65535 параметров в запросе)."""
    if not external_ids:
        return {}
    unique = list(dict.fromkeys(external_ids))
    out: dict[str, IncidentRegistry] = {}
    for i in range(0, len(unique), REGISTRY_IN_CHUNK):
        chunk = unique[i : i + REGISTRY_IN_CHUNK]
        stmt = select(IncidentRegistry).where(IncidentRegistry.external_id.in_(chunk))
        if resolved_only:
            stmt = stmt.where(IncidentRegistry.manually_resolved.is_(True))
        for row in session.scalars(stmt).all():
            out[row.external_id] = row
    return out


def lookup_registry_resolved(session: Session, external_ids: list[str]) -> dict[str, IncidentRegistry]:
    return _lookup_incident_registry(session, external_ids, resolved_only=True)


def sync_incident_registry(session: Session, task_id: str, incidents: list[dict]) -> None:
    """Регистрирует ID обращений для дедупа и переноса статуса «решено» между загрузками."""
    now = datetime.now(timezone.utc).isoformat()
    ext_items: list[tuple[str, dict]] = []
    for item in incidents:
        ext = _registry_external_id(item.get("row_id", ""), item.get("id_обращения", ""))
        if ext:
            ext_items.append((ext, item))
    if not ext_items:
        return

    existing = _lookup_incident_registry(session, [ext for ext, _ in ext_items])
    for ext, item in ext_items:
        reg = existing.get(ext)
        if reg is None:
            reg = IncidentRegistry(
                external_id=ext,
                incident_number=item.get("incident_number"),
                manually_resolved=bool(item.get("manually_resolved")),
                resolved_at=item.get("resolved_at"),
                resolved_note=item.get("resolved_note"),
                first_task_id=task_id,
                last_task_id=task_id,
                updated_at=now,
            )
            session.add(reg)
            existing[ext] = reg
            continue
        reg.last_task_id = task_id
        reg.updated_at = now
        if item.get("incident_number"):
            reg.incident_number = item.get("incident_number")
        if item.get("manually_resolved") and not reg.manually_resolved:
            reg.manually_resolved = True
            reg.resolved_at = item.get("resolved_at")
            reg.resolved_note = item.get("resolved_note")
            _propagate_registry_resolved_flag(session, ext, True)


def mark_incident_resolved(
    task_id: str,
    row_id: str,
    *,
    note: str = "",
    resolved: bool = True,
) -> dict | None:
    """Отметить обращение решённым (или снять отметку) по row_id / ID кабинета."""
    now = datetime.now(timezone.utc).isoformat() if resolved else None
    with get_session() as session:
        row = session.scalar(
            select(StoredIncident).where(
                StoredIncident.task_id == task_id,
                StoredIncident.row_id == row_id,
            )
        )
        if row is None:
            return None

        row.manually_resolved = resolved
        row.resolved_at = now if resolved else None
        row.resolved_note = note.strip() or None if resolved else None
        _sync_row_is_resolved(row)

        ext = _registry_external_id(row.row_id, row.row_id)
        if ext:
            reg = session.get(IncidentRegistry, ext)
            if reg is None:
                reg = IncidentRegistry(
                    external_id=ext,
                    incident_number=row.incident_number,
                    first_task_id=task_id,
                    last_task_id=task_id,
                    updated_at=now or datetime.now(timezone.utc).isoformat(),
                )
                session.add(reg)
            reg.manually_resolved = resolved
            reg.resolved_at = now if resolved else None
            reg.resolved_note = row.resolved_note
            reg.last_task_id = task_id
            reg.updated_at = now or datetime.now(timezone.utc).isoformat()
            _propagate_registry_resolved_flag(session, ext, resolved)

        return {
            "task_id": task_id,
            "row_id": row_id,
            "external_id": ext,
            "manually_resolved": resolved,
            "resolved_at": row.resolved_at,
            "resolved_note": row.resolved_note,
        }


def dataframe_to_incident_rows(df, *, session: Session | None = None) -> list[dict]:
    from app.agency_mapping import resolve_agency, resolve_agency_email, resolve_municipality_admin

    external_ids: list[str] = []
    pre_rows: list[dict] = []
    for _, row in df.iterrows():
        municipality = str(row.get("муниципалитет", "")).strip()
        settlement = str(row.get("населенный_пункт", "")).strip()
        street = str(row.get("улица", "")).strip()
        house = str(row.get("дом", "")).strip()
        group = str(row.get("группа", "")).strip()
        row_id = str(row.get("row_id", "")).strip() or str(row.name)
        id_обращения = str(row.get("id_обращения", "")).strip()
        ext = _registry_external_id(row_id, id_обращения)
        if ext:
            external_ids.append(ext)
        pre_rows.append((row, municipality, settlement, street, house, group, row_id, id_обращения, ext))

    resolved_registry: dict[str, IncidentRegistry] = {}
    if session is not None and external_ids:
        resolved_registry = lookup_registry_resolved(session, list(set(external_ids)))

    rows: list[dict] = []
    for row, municipality, settlement, street, house, group, row_id, id_обращения, ext in pre_rows:
        row_dict = {
            "муниципалитет": municipality,
            "населенный_пункт": settlement,
            "улица": street,
            "дом": house,
        }
        address_line, _ = geocode_query_from_row(row_dict)
        admin = resolve_municipality_admin(municipality)
        try:
            severity = int(row.get("severity", 0))
        except (TypeError, ValueError):
            severity = 0
        is_problem = bool(row.get("is_problem", severity >= 1))
        manually_resolved = False
        resolved_at = None
        resolved_note = None
        outcome_val = str(row.get("итог", "")).strip() or None

        if ext and ext in resolved_registry:
            reg = resolved_registry[ext]
            manually_resolved = True
            resolved_at = reg.resolved_at
            resolved_note = reg.resolved_note
        elif is_resolved_outcome(outcome_val):
            manually_resolved = True
        is_resolved = _compute_is_resolved(
            manually_resolved=manually_resolved,
            outcome=outcome_val,
            registry_resolved=bool(ext and ext in resolved_registry),
        )
        rows.append(
            {
                "task_id": "",
                "row_id": row_id,
                "incident_number": str(row.get("номер_инцидента", "")).strip() or None,
                "created_at": str(row.get("дата_создания", "")).strip() or None,
                "closed_at": str(row.get("дата_закрытия", "")).strip() or None,
                "workflow_step": str(row.get("шаг_инцидента", "")).strip() or None,
                "outcome": outcome_val,
                "group_name": group,
                "topic": str(row.get("тема", "")).strip(),
                "municipality": municipality,
                "settlement": settlement or None,
                "street": street or None,
                "house": house or None,
                "text": str(row.get("текст", "")).strip(),
                "severity": severity,
                "is_problem": is_problem,
                "agency": resolve_agency(group),
                "agency_email": resolve_agency_email(resolve_agency(group)),
                "municipality_admin": admin.get("administration"),
                "municipality_email": admin.get("email"),
                "municipality_phone": admin.get("phone"),
                "address_line": address_line,
                "has_address": has_street_address(row_dict),
                "lat": None,
                "lng": None,
                "manually_resolved": manually_resolved,
                "is_resolved": is_resolved,
                "resolved_at": resolved_at,
                "resolved_note": resolved_note,
            }
        )
    return rows
