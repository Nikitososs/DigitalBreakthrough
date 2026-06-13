"""Общие хелперы для роутеров API.

Перенесены дословно из src/main.py — здесь живут ветки live0000
(`_is_live_task`) и проверки готовности задач (`_require_completed`),
чтобы все роутеры использовали единую логику источника данных.
"""

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import Response

from app.config.paths import DATA_DIR
from app.db.repository import has_stored_job, list_stored_jobs
from app.incident_store import register_task_from_disk
from app.config.paths import JOBS_DIR
from app.complaint_submit import submit_citizen_complaint
from app.live_stream import LIVE_STREAM_TASK_ID, ensure_live_stream_job
from app.pdf_report import build_district_pdf, content_disposition_header
from app.report import build_district_report
from schemas import (
    DistrictReport,
    JobStatus,
    LiveEventResponse,
    PipelineStep,
    SubmitComplaintRequest,
    SubmitComplaintResponse,
)
from src import jobs


def _is_live_task(task_id: str) -> bool:
    return task_id == LIVE_STREAM_TASK_ID


def _ensure_live_task(task_id: str) -> None:
    if _is_live_task(task_id):
        ensure_live_stream_job()


def _live_job_status() -> JobStatus:
    ensure_live_stream_job()
    row = next((r for r in list_stored_jobs() if r["task_id"] == LIVE_STREAM_TASK_ID), None)
    try:
        report = jobs.get_report(LIVE_STREAM_TASK_ID)
        stats = report.get("stats") or {}
    except FileNotFoundError:
        stats = {}
    return JobStatus(
        task_id=LIVE_STREAM_TASK_ID,
        status="completed",
        message="Live-поток граждан",
        created_at=(row or {}).get("created_at"),
        filename=(row or {}).get("filename") or "Live-поток граждан",
        rows_processed=stats.get("rows_processed") or (row or {}).get("rows_total"),
        stats=stats,
        steps=[],
        progress=1.0,
    )


def _get_task_report(task_id: str) -> dict:
    _ensure_live_task(task_id)
    try:
        return jobs.get_report(task_id)
    except KeyError:
        raise HTTPException(404, "Задача не найдена") from None
    except jobs.JobNotReadyError as exc:
        raise HTTPException(409, f"Задача ещё не готова: {exc.status}") from exc
    except FileNotFoundError:
        raise HTTPException(404, "Отчёт ещё не готов") from None


def _job_status(task_id: str) -> JobStatus:
    if _is_live_task(task_id):
        return _live_job_status()
    job = jobs.get_job(task_id)
    if job is None:
        raise HTTPException(404, "Задача не найдена")
    return JobStatus(
        task_id=job["task_id"],
        status=job["status"],
        message=job.get("message"),
        created_at=job.get("created_at"),
        filename=job.get("filename"),
        rows_processed=job.get("rows_processed"),
        stats=job.get("stats"),
        steps=[PipelineStep(**s) for s in (job.get("steps") or [])],
        progress=job.get("progress"),
    )


def _require_completed(task_id: str) -> Path:
    try:
        return jobs.require_completed(task_id)
    except KeyError:
        raise HTTPException(404, "Задача не найдена") from None
    except jobs.JobNotReadyError as exc:
        raise HTTPException(409, f"Статус: {exc.status}") from exc


def _ensure_task_in_db(task_id: str) -> None:
    if has_stored_job(task_id):
        return
    try:
        register_task_from_disk(task_id, JOBS_DIR)
    except FileNotFoundError as exc:
        raise HTTPException(
            404,
            "Задача не в базе. Дождитесь завершения анализа или импортируйте в архив.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


def _require_task_data(task_id: str) -> None:
    if _is_live_task(task_id):
        ensure_live_stream_job()
        return
    if has_stored_job(task_id):
        return
    try:
        jobs.require_completed(task_id)
    except KeyError:
        raise HTTPException(404, "Задача не найдена") from None
    except jobs.JobNotReadyError as exc:
        raise HTTPException(409, f"Задача не готова: {exc.status}") from exc


MAX_LIST_GEOCODE_FRESH = 10


def _resolve_list_geocode_max_fresh(
    geocode: bool,
    geocode_cache_only: bool,
    geocode_max_fresh: int | None,
) -> int | None:
    """Ограничивает Nominatim при списке обращений — иначе API блокируется на минуты."""
    if not geocode:
        return None
    if geocode_cache_only:
        return 0
    if geocode_max_fresh is None:
        return 0
    return min(max(geocode_max_fresh, 0), MAX_LIST_GEOCODE_FRESH)


def _submit_complaint_body(body: SubmitComplaintRequest, task_id: str) -> SubmitComplaintResponse:
    try:
        event = submit_citizen_complaint(
            task_id,
            text=body.text,
            group=body.group,
            topic=body.topic,
            municipality=body.municipality,
            settlement=body.settlement,
            street=body.street,
            house=body.house,
            geocode_cache=DATA_DIR / "geocode_cache.json",
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Не удалось сохранить обращение: {exc}") from exc
    return SubmitComplaintResponse(
        incident=LiveEventResponse(**event),
        message="Обращение принято и появится в live-потоке",
    )


def _collect_district_reports(report: dict, task_id: str) -> list[DistrictReport]:
    labeled_df = None
    try:
        labeled_df = jobs.get_labeled_df(task_id)
    except FileNotFoundError:
        pass

    districts: list[DistrictReport] = []
    for row in report.get("all", []):
        district_id = int(row.get("district_id", row.get("rank", 0)))
        custom_summary = jobs.get_district_summary(task_id, district_id)
        result = build_district_report(
            report,
            district_id,
            analytical_summary=custom_summary,
            labeled_df=labeled_df,
        )
        if result is not None:
            districts.append(result.data)
    return districts


def _district_report_pdf_response(data: DistrictReport) -> Response:
    try:
        pdf_bytes = build_district_pdf(data)
    except Exception as exc:
        raise HTTPException(500, f"Не удалось сформировать PDF: {exc}") from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": content_disposition_header(
                data.district_id,
                data.district_name,
            ),
        },
    )


def _department_zip_response(zip_bytes: bytes) -> Response:
    from urllib.parse import quote

    filename = "zeroproblems_vedomstva.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote("zeroproblems_otchety_vedomstva.zip")}'
            ),
        },
    )


def _load_labeled_for_export(task_id: str):
    if _is_live_task(task_id):
        _ensure_live_task(task_id)
        try:
            labeled_df = jobs.get_labeled_df(task_id)
        except FileNotFoundError:
            raise HTTPException(404, "Размеченные данные ещё не готовы") from None
        if labeled_df is None or labeled_df.empty:
            raise HTTPException(404, "В live-потоке пока нет обращений")
        return labeled_df
    _require_completed(task_id)
    try:
        return jobs.get_labeled_df(task_id)
    except FileNotFoundError:
        raise HTTPException(404, "Размеченные данные ещё не готовы") from None
