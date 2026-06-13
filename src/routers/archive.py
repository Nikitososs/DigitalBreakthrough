"""Архив задач в БД и управление кэшем на диске."""

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import require_permission
from app.auth.permissions import Permission

from app.config.paths import JOBS_DIR
from app.db.repository import (
    canonical_content_hashes,
    delete_stored_job,
    has_stored_job,
    list_global_facets_from_db,
    list_stored_jobs,
    reconcile_duplicate_stored_jobs,
    resolve_default_task_id,
)
from app.file_fingerprint import find_job_input_file, sha256_file
from app.incident_store import import_task_from_disk
from app.live_stream import LIVE_STREAM_TASK_ID, ensure_live_stream_job
from schemas import (
    ArchiveCacheDeleteRequest,
    ArchiveCacheDeleteResponse,
    ArchiveImportResponse,
    ArchiveJobItem,
    ArchiveJobsResponse,
    TaskIncidentFacetsResponse,
)
from src import jobs

router = APIRouter()
public_router = APIRouter()


def _cache_content_hash(task_id: str, job_meta: dict | None = None) -> str | None:
    if job_meta and job_meta.get("content_hash"):
        return str(job_meta["content_hash"])
    input_path = find_job_input_file(JOBS_DIR / task_id)
    if input_path is None:
        return None
    return sha256_file(input_path)


def _archive_job_item(row: dict, *, in_cache: bool, known_hashes: set[str] | None = None) -> ArchiveJobItem:
    content_hash = row.get("content_hash")
    is_dup_candidate = False
    if known_hashes is not None and content_hash and not row.get("is_duplicate"):
        is_dup_candidate = content_hash in known_hashes and row.get("incident_count", 0) == 0
    return ArchiveJobItem(
        **row,
        in_cache=in_cache,
        is_duplicate_candidate=is_dup_candidate,
    )


@router.get(
    "/archive/jobs",
    response_model=ArchiveJobsResponse,
    summary="Список задач в базе данных",
    dependencies=[Depends(require_permission(Permission.ARCHIVE_READ))],
)
async def list_archive_jobs():
    ensure_live_stream_job()
    reconcile_duplicate_stored_jobs()
    all_stored = list_stored_jobs()
    live_row = next((r for r in all_stored if r["task_id"] == LIVE_STREAM_TASK_ID), None)
    stored_rows = [
        row for row in all_stored if row["task_id"] != LIVE_STREAM_TASK_ID
    ]
    canonical_hashes = canonical_content_hashes()

    jobs_out: list[ArchiveJobItem] = []
    duplicates_out: list[ArchiveJobItem] = []
    for row in stored_rows:
        item = _archive_job_item(
            row,
            in_cache=jobs.get_job(row["task_id"]) is not None,
        )
        if row.get("is_duplicate"):
            duplicates_out.append(item)
        else:
            jobs_out.append(item)

    importable: list[ArchiveJobItem] = []
    for job in jobs.list_jobs():
        tid = job.get("task_id")
        if not tid or tid in {r["task_id"] for r in stored_rows} or job.get("status") != "completed":
            continue
        stats = job.get("stats") or {}
        content_hash = _cache_content_hash(tid, job)
        is_dup_candidate = bool(content_hash and content_hash in canonical_hashes)
        importable.append(
            ArchiveJobItem(
                task_id=tid,
                filename=str(job.get("filename") or ""),
                created_at=str(job.get("created_at") or ""),
                stored_at="",
                rows_total=int(job.get("rows_processed") or stats.get("rows_processed") or 0),
                problem_count=stats.get("problem_count"),
                municipality_count=stats.get("municipality_count"),
                incident_count=0,
                in_cache=True,
                is_duplicate=is_dup_candidate,
                is_duplicate_candidate=is_dup_candidate,
            )
        )

    jobs_out.sort(key=lambda j: j.stored_at or j.created_at, reverse=True)
    duplicates_out.sort(key=lambda j: j.stored_at or j.created_at, reverse=True)
    importable.sort(key=lambda j: j.created_at, reverse=True)
    live_job = (
        ArchiveJobItem(**live_row, in_cache=False)
        if live_row is not None
        else None
    )
    return ArchiveJobsResponse(
        jobs=jobs_out,
        duplicates=duplicates_out,
        importable=importable,
        default_task_id=resolve_default_task_id(),
        live_job=live_job,
    )


@public_router.get(
    "/reference/facets",
    response_model=TaskIncidentFacetsResponse,
    summary="Справочники групп, тем и МО из базы",
)
async def get_reference_facets(
    severity_min: int = 0,
    severity_max: int = 4,
):
    return TaskIncidentFacetsResponse(**list_global_facets_from_db(
        severity_min=severity_min,
        severity_max=severity_max,
    ))


@router.post(
    "/archive/jobs/{task_id}/import",
    response_model=ArchiveImportResponse,
    summary="Импорт завершённой задачи из cache в БД",
    dependencies=[Depends(require_permission(Permission.ARCHIVE_WRITE))],
)
async def import_archive_job(task_id: str):
    if has_stored_job(task_id):
        stored = next((j for j in list_stored_jobs() if j["task_id"] == task_id), None)
        if stored and stored.get("is_duplicate"):
            return ArchiveImportResponse(
                task_id=task_id,
                incident_count=0,
                message=f"Дубликат файла (оригинал {stored.get('duplicate_of_task_id')})",
                is_duplicate=True,
                duplicate_of_task_id=stored.get("duplicate_of_task_id"),
            )
        return ArchiveImportResponse(
            task_id=task_id,
            incident_count=int(stored["incident_count"]) if stored else 0,
            message="Уже в базе",
        )
    try:
        result = import_task_from_disk(task_id, JOBS_DIR)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
    if result.is_duplicate:
        return ArchiveImportResponse(
            task_id=task_id,
            incident_count=0,
            message=f"Файл уже в базе (оригинал {result.duplicate_of_task_id}), обращения не импортированы",
            is_duplicate=True,
            duplicate_of_task_id=result.duplicate_of_task_id,
        )
    return ArchiveImportResponse(
        task_id=task_id,
        incident_count=result.incident_count,
        message=f"Импортировано {result.incident_count} обращений",
    )


@router.delete(
    "/archive/jobs/{task_id}",
    summary="Удалить задачу из базы (файлы cache не трогаются)",
    dependencies=[Depends(require_permission(Permission.ARCHIVE_WRITE))],
)
async def remove_archive_job(task_id: str):
    if not delete_stored_job(task_id):
        raise HTTPException(404, "Задачи нет в базе")
    return {"ok": True, "task_id": task_id}


@router.delete(
    "/archive/cache/{task_id}",
    summary="Удалить завершённую задачу из кэша на диске",
    dependencies=[Depends(require_permission(Permission.ARCHIVE_WRITE))],
)
async def remove_cached_job(task_id: str):
    from src import jobs as job_store

    if has_stored_job(task_id):
        raise HTTPException(409, "Задача уже в базе — удалите из базы отдельно")
    if not job_store.delete_cached_job(task_id):
        raise HTTPException(404, "Задачи нет в кэше")
    return {"ok": True, "task_id": task_id}


@router.post(
    "/archive/cache/delete",
    response_model=ArchiveCacheDeleteResponse,
    summary="Удалить выбранные задачи из кэша",
    dependencies=[Depends(require_permission(Permission.ARCHIVE_WRITE))],
)
async def remove_cached_jobs_bulk(body: ArchiveCacheDeleteRequest):
    from src import jobs as job_store

    in_db = [tid for tid in body.task_ids if has_stored_job(tid)]
    if in_db:
        raise HTTPException(
            409,
            f"Задачи уже в базе: {', '.join(in_db)}. Удалите их из раздела «В базе».",
        )
    result = job_store.delete_cached_jobs(body.task_ids)
    if result["count"] == 0:
        raise HTTPException(404, "Ни одной задачи не найдено в кэше")
    return ArchiveCacheDeleteResponse(**result)
