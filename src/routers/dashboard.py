"""Дашборд региона и отчёты по муниципалитетам (JSON + PDF)."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import require_permission
from app.auth.permissions import Permission

from app.db.repository import resolve_default_task_id
from app.forecast import ALLOWED_HORIZONS
from app.forecast_cache import get_forecast_ai_summary, get_forecast_response
from app.report import build_dashboard, build_district_report
from app.report_dates import enrich_report_period
from schemas import DashboardResponse, DistrictReportResponse, ForecastAiSummaryResponse, ForecastResponse
from src import jobs
from src.routers._common import (
    _district_report_pdf_response,
    _ensure_live_task,
    _get_task_report,
)

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Данные дашборда по последней или указанной задаче",
    dependencies=[Depends(require_permission(Permission.DASHBOARD))],
)
async def get_dashboard(task_id: str | None = None):
    resolved_id = task_id
    try:
        if task_id:
            _ensure_live_task(task_id)
            report = jobs.get_report(task_id)
        else:
            resolved_id = resolve_default_task_id()
            if resolved_id:
                report = jobs.get_report(resolved_id)
            else:
                completed = [
                    j for j in jobs.list_jobs() if j.get("status") == "completed"
                ]
                if not completed:
                    raise HTTPException(404, "Нет данных в базе. Загрузите датасет.")
                completed.sort(key=lambda j: j.get("created_at") or "", reverse=True)
                resolved_id = completed[0]["task_id"]
                report = jobs.get_report(resolved_id)
    except KeyError:
        raise HTTPException(404, "Задача не найдена") from None
    except jobs.JobNotReadyError as exc:
        raise HTTPException(409, f"Задача ещё не готова: {exc.status}") from exc
    except FileNotFoundError:
        raise HTTPException(404, "Отчёт ещё не готов") from None
    if resolved_id:
        cache_dir = jobs.job_path(resolved_id) / "cache"
        if cache_dir.is_dir():
            enrich_report_period(report, cache_dir)
    return build_dashboard(report)


@router.get(
    "/districts/{district_id}/report",
    response_model=DistrictReportResponse,
    summary="Отчёт по муниципалитету",
    dependencies=[Depends(require_permission(Permission.DASHBOARD))],
)
async def get_district_report(district_id: int, task_id: str | None = None):
    if not task_id:
        completed = [j for j in jobs.list_jobs() if j.get("status") == "completed"]
        if not completed:
            raise HTTPException(404, "Нет завершённых задач")
        completed.sort(key=lambda j: j.get("created_at") or "", reverse=True)
        task_id = completed[0]["task_id"]

    report = _get_task_report(task_id)

    labeled_df = None
    try:
        labeled_df = jobs.get_labeled_df(task_id)
    except FileNotFoundError:
        pass

    custom_summary = jobs.get_district_summary(task_id, district_id)
    result = build_district_report(
        report,
        district_id,
        analytical_summary=custom_summary,
        labeled_df=labeled_df,
    )
    if result is None:
        raise HTTPException(404, f"Район с id={district_id} не найден")
    return result


@router.get(
    "/districts/{district_id}/report.pdf",
    summary="PDF-отчёт по муниципалитету",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def get_district_report_pdf(district_id: int, task_id: str | None = None):
    if not task_id:
        completed = [j for j in jobs.list_jobs() if j.get("status") == "completed"]
        if not completed:
            raise HTTPException(404, "Нет завершённых задач")
        completed.sort(key=lambda j: j.get("created_at") or "", reverse=True)
        task_id = completed[0]["task_id"]

    report = _get_task_report(task_id)

    labeled_df = None
    try:
        labeled_df = jobs.get_labeled_df(task_id)
    except FileNotFoundError:
        pass

    custom_summary = jobs.get_district_summary(task_id, district_id)
    result = build_district_report(
        report,
        district_id,
        analytical_summary=custom_summary,
        labeled_df=labeled_df,
    )
    if result is None:
        raise HTTPException(404, f"Район с id={district_id} не найден")
    return _district_report_pdf_response(result.data)


@router.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Прогноз проблемных обращений по всему архиву БД",
    dependencies=[Depends(require_permission(Permission.DASHBOARD))],
)
async def get_forecast(horizon_weeks: int = 4):
    if horizon_weeks not in ALLOWED_HORIZONS:
        raise HTTPException(
            400,
            f"horizon_weeks должен быть одним из: {', '.join(map(str, ALLOWED_HORIZONS))}",
        )

    return get_forecast_response(horizon_weeks)


@router.post(
    "/forecast/ai-summary",
    response_model=ForecastAiSummaryResponse,
    summary="AI-сводка по прогнозу (все графики и тренды)",
    dependencies=[Depends(require_permission(Permission.DASHBOARD))],
)
async def post_forecast_ai_summary(horizon_weeks: int = 4, force: bool = False):
    if horizon_weeks not in ALLOWED_HORIZONS:
        raise HTTPException(
            400,
            f"horizon_weeks должен быть одним из: {', '.join(map(str, ALLOWED_HORIZONS))}",
        )
    try:
        return await asyncio.to_thread(get_forecast_ai_summary, horizon_weeks, force=force)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Не удалось сгенерировать сводку: {exc}") from exc
