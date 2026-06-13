"""Жизненный цикл задач: загрузка датасета, статусы, JSON-отчёт и справки."""

import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from app.auth.deps import require_permission
from app.auth.permissions import Permission
from app.file_fingerprint import sha256_file
from fastapi.responses import PlainTextResponse

from schemas import DatasetUploadResponse, JobStatus, PipelineOptions
from src import jobs
from src.routers._common import (
    _get_task_report,
    _is_live_task,
    _job_status,
    _require_completed,
)

router = APIRouter()


@router.post(
    "/dataset/upload",
    response_model=DatasetUploadResponse,
    summary="Загрузка Excel и запуск обработки",
    dependencies=[Depends(require_permission(Permission.JOBS_UPLOAD))],
)
async def upload_dataset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    skip_summary: bool = False,
    batch_size: int = 16,
    nrows: int | None = None,
    model: str | None = None,
    llm_fast_mode: bool = True,
):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Нужен файл .xlsx или .xls")

    task_id = str(uuid.uuid4())[:8]
    job_dir = jobs.job_path(task_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    dest = job_dir / f"input{Path(file.filename).suffix}"
    content = await file.read()
    dest.write_bytes(content)

    options = PipelineOptions(
        skip_summary=skip_summary,
        batch_size=batch_size,
        nrows=nrows,
        model=model,
        llm_fast_mode=llm_fast_mode,
    )
    jobs.create_job(task_id, file.filename, content_hash=sha256_file(dest))
    background_tasks.add_task(jobs.run_job, task_id, dest, options)

    return DatasetUploadResponse(
        task_id=task_id,
        filename=file.filename,
        message=f"Датасет принят, задача {task_id} в обработке",
        rows_processed=0,
    )


@router.get(
    "/jobs",
    response_model=list[JobStatus],
    summary="Список задач",
    dependencies=[Depends(require_permission(Permission.JOBS_READ))],
)
async def list_jobs():
    return [_job_status(j["task_id"]) for j in jobs.list_jobs() if jobs.get_job(j["task_id"])]


@router.get(
    "/jobs/{task_id}",
    response_model=JobStatus,
    summary="Статус задачи",
    dependencies=[Depends(require_permission(Permission.JOBS_READ))],
)
async def get_job(task_id: str):
    return _job_status(task_id)


@router.get(
    "/jobs/{task_id}/report",
    summary="Полный JSON-отчёт",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def get_job_report(task_id: str):
    if _is_live_task(task_id):
        return _get_task_report(task_id)
    _require_completed(task_id)
    try:
        return jobs.get_report(task_id)
    except FileNotFoundError:
        raise HTTPException(404, "Отчёт ещё не готов") from None


@router.get(
    "/jobs/{task_id}/summary",
    summary="Текстовая справка для руководства",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def get_job_summary(task_id: str):
    if _is_live_task(task_id):
        report = _get_task_report(task_id)
        text = report.get("summary_text", "")
        if not text:
            raise HTTPException(404, "Справка не найдена")
        return PlainTextResponse(text, media_type="text/markdown")
    out = _require_completed(task_id)
    path = out / "executive_summary.md"
    if not path.exists():
        report = jobs.get_report(task_id)
        text = report.get("summary_text", "")
        if not text:
            raise HTTPException(404, "Справка не найдена")
        return PlainTextResponse(text, media_type="text/markdown")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")


@router.get(
    "/jobs/{task_id}/summary/briefs",
    summary="Справки по Top-3 и Top-10",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def get_job_municipality_briefs(task_id: str):
    out = _require_completed(task_id)
    path = out / "municipality_briefs.md"
    if not path.exists():
        raise HTTPException(404, "Справки по муниципалитетам не найдены — перезапустите обработку")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")
