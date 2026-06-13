"""Обращения задачи: список, карта, удаление citizen-*, геокод и warmup."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import require_permission
from app.auth.permissions import Permission

from app.config.paths import DATA_DIR, JOBS_DIR
from app.db.repository import (
    delete_citizen_incident,
    geocode_and_save_incident,
    has_stored_job,
    mark_incident_resolved,
)
from app.geocode_worker import get_warmup_status, start_warmup, stop_warmup
from app.task_incidents import (
    list_incident_facets,
    list_task_incident_packages,
    list_task_incidents,
    list_task_map_markers,
)
from schemas import (
    GeocodeWarmupStatusResponse,
    IncidentResolveRequest,
    IncidentResolveResponse,
    TaskIncidentFacetsResponse,
    TaskIncidentItem,
    TaskIncidentPackagesResponse,
    TaskIncidentsResponse,
    TaskMapMarkersResponse,
)
from src.routers._common import _require_task_data, _resolve_list_geocode_max_fresh

router = APIRouter()


@router.get(
    "/jobs/{task_id}/incidents",
    response_model=TaskIncidentsResponse,
    summary="Обращения задачи для оператора / экстренного режима",
    dependencies=[Depends(require_permission(Permission.INCIDENTS_READ))],
)
async def get_task_incidents(
    task_id: str,
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
    geocode_cache_only: bool = False,
    geocode_max_fresh: int | None = None,
):
    _require_task_data(task_id)
    resolved_max_fresh = _resolve_list_geocode_max_fresh(geocode, geocode_cache_only, geocode_max_fresh)

    try:
        payload = await asyncio.to_thread(
            list_task_incidents,
            task_id,
            JOBS_DIR,
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
            limit=min(max(limit, 1), 5000),
            offset=max(offset, 0),
            geocode=geocode,
            geocode_cache=DATA_DIR / "geocode_cache.json" if geocode else None,
            geocode_cache_only=geocode_cache_only if geocode else False,
            geocode_max_fresh=resolved_max_fresh,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return TaskIncidentsResponse(**payload)


@router.get(
    "/jobs/{task_id}/incidents/packages",
    response_model=TaskIncidentPackagesResponse,
    summary="Пакеты обращений по ведомствам (сборка на сервере)",
    dependencies=[Depends(require_permission(Permission.INCIDENTS_READ))],
)
async def get_task_incident_packages(
    task_id: str,
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
):
    _require_task_data(task_id)
    try:
        payload = await asyncio.to_thread(
            list_task_incident_packages,
            task_id,
            JOBS_DIR,
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
            limit=min(max(limit, 1), 500),
            offset=max(offset, 0),
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return TaskIncidentPackagesResponse(**payload)


@router.get(
    "/jobs/{task_id}/incidents/map-markers",
    response_model=TaskMapMarkersResponse,
    summary="Лёгкие координаты geocoded обращений для карты",
    dependencies=[Depends(require_permission(Permission.INCIDENTS_READ))],
)
async def get_task_map_markers(
    task_id: str,
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
    zoom: int | None = None,
    limit: int = 5000,
    offset: int = 0,
):
    _require_task_data(task_id)
    resolved_limit = min(max(limit, 1), 10000)
    if zoom is not None:
        if zoom < 8:
            resolved_limit = min(resolved_limit, 1500)
        elif zoom < 11:
            resolved_limit = min(resolved_limit, 3000)
    try:
        payload = await asyncio.to_thread(
            list_task_map_markers,
            task_id,
            JOBS_DIR,
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
            limit=resolved_limit,
            offset=max(offset, 0),
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return TaskMapMarkersResponse(**payload)


@router.delete(
    "/jobs/{task_id}/incidents/{row_id}",
    summary="Удалить обращение гражданина (live-поток)",
    dependencies=[Depends(require_permission(Permission.INCIDENTS_WRITE))],
)
async def remove_citizen_incident(task_id: str, row_id: str):
    _require_task_data(task_id)
    try:
        deleted = delete_citizen_incident(task_id, row_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not deleted:
        raise HTTPException(404, "Обращение не найдено")
    return {"ok": True, "row_id": row_id}


@router.post(
    "/jobs/{task_id}/incidents/{row_id}/resolve",
    response_model=IncidentResolveResponse,
    summary="Отметить обращение / пробел решённым (ключ — ID кабинета / row_id)",
    dependencies=[Depends(require_permission(Permission.INCIDENTS_WRITE))],
)
async def resolve_task_incident(task_id: str, row_id: str, body: IncidentResolveRequest):
    _require_task_data(task_id)
    result = await asyncio.to_thread(
        mark_incident_resolved,
        task_id,
        row_id,
        note=body.note or "",
        resolved=body.resolved,
    )
    if result is None:
        raise HTTPException(404, "Обращение не найдено")
    return IncidentResolveResponse(**result)


@router.post(
    "/jobs/{task_id}/incidents/{row_id}/geocode",
    response_model=TaskIncidentItem,
    summary="Геокодировать обращение (Nominatim → кэш + Postgres) и сохранить координаты",
    dependencies=[Depends(require_permission(Permission.INCIDENTS_WRITE))],
)
async def geocode_citizen_incident_route(
    task_id: str,
    row_id: str,
    cache_only: bool = False,
):
    _require_task_data(task_id)
    try:
        item = await asyncio.to_thread(
            geocode_and_save_incident,
            task_id,
            row_id,
            geocode_cache=DATA_DIR / "geocode_cache.json",
            cache_only=cache_only,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return TaskIncidentItem(**item)


@router.post(
    "/jobs/{task_id}/geocode/warmup",
    response_model=GeocodeWarmupStatusResponse,
    summary="Запустить фоновый прогрев геокодов по уникальным адресам задачи",
    dependencies=[Depends(require_permission(Permission.GEOCODE_WARMUP))],
)
async def start_geocode_warmup(task_id: str):
    _require_task_data(task_id)
    if not has_stored_job(task_id):
        raise HTTPException(404, "Задача не найдена в БД")
    payload = await asyncio.to_thread(start_warmup, task_id)
    return GeocodeWarmupStatusResponse(**payload)


@router.get(
    "/jobs/{task_id}/geocode/warmup",
    response_model=GeocodeWarmupStatusResponse,
    summary="Статус фонового прогрева геокодов",
    dependencies=[Depends(require_permission(Permission.GEOCODE_WARMUP))],
)
async def geocode_warmup_status(task_id: str):
    _require_task_data(task_id)
    payload = await asyncio.to_thread(get_warmup_status, task_id)
    return GeocodeWarmupStatusResponse(**payload)


@router.delete(
    "/jobs/{task_id}/geocode/warmup",
    response_model=GeocodeWarmupStatusResponse,
    summary="Остановить фоновый прогрев геокодов",
    dependencies=[Depends(require_permission(Permission.GEOCODE_WARMUP))],
)
async def stop_geocode_warmup(task_id: str):
    _require_task_data(task_id)
    payload = await asyncio.to_thread(stop_warmup, task_id)
    return GeocodeWarmupStatusResponse(**payload)


@router.get(
    "/jobs/{task_id}/incidents/facets",
    response_model=TaskIncidentFacetsResponse,
    summary="Справочники для фильтров оператора",
    dependencies=[Depends(require_permission(Permission.INCIDENTS_READ))],
)
async def get_task_incident_facets(
    task_id: str,
    severity_min: int = 1,
    severity_max: int = 4,
    municipality: str | None = None,
    group: str | None = None,
    resolved: bool | None = None,
):
    _require_task_data(task_id)

    try:
        payload = list_incident_facets(
            task_id,
            JOBS_DIR,
            severity_min=severity_min,
            severity_max=severity_max,
            municipality=municipality,
            group=group,
            resolved=resolved,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return TaskIncidentFacetsResponse(**payload)
