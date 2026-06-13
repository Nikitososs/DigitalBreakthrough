"""Отчёты: Excel, сводные PDF, архивы для ведомств, LLM-генерация и письма."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.auth.deps import require_permission
from app.auth.permissions import Permission
from fastapi.responses import FileResponse, Response

from app.agency_report import build_department_preview, build_department_reports_zip
from app.config.paths import DATA_DIR
from app.pdf_report import build_region_pdf, content_disposition_region_header
from app.report_excel import build_full_excel_from_report, build_top10_excel_from_report
from schemas import (
    ComposeEmailRequest,
    ComposeEmailResponse,
    DepartmentReportsPreview,
    DepartmentReportsStatus,
    DistrictReport,
    GenerateReportRequest,
    GenerateReportResponse,
    RegionPdfRequest,
)
from src import jobs
from src.routers._common import (
    _collect_district_reports,
    _department_zip_response,
    _district_report_pdf_response,
    _get_task_report,
    _is_live_task,
    _load_labeled_for_export,
    _require_completed,
)

router = APIRouter()

_district_tasks: dict[str, dict] = {}
_department_export_tasks: dict[str, dict] = {}


@router.get(
    "/jobs/{task_id}/excel",
    summary="Скачать полный Excel-отчёт",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def download_excel(task_id: str):
    if _is_live_task(task_id):
        report = _get_task_report(task_id)
        out = DATA_DIR / "live_export"
        path = build_full_excel_from_report(report, out)
        return FileResponse(path, filename="live_all_municipalities.xlsx")
    out = _require_completed(task_id)
    try:
        report = jobs.get_report(task_id)
    except FileNotFoundError:
        raise HTTPException(404, "Отчёт не найден") from None
    path = build_full_excel_from_report(report, out)
    return FileResponse(path, filename="report_top_districts.xlsx")


@router.get(
    "/jobs/{task_id}/excel/top10",
    summary="Скачать Excel по Top-10",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def download_excel_top10(task_id: str):
    if _is_live_task(task_id):
        report = _get_task_report(task_id)
        out = DATA_DIR / "live_export"
        out.mkdir(parents=True, exist_ok=True)
        path = build_top10_excel_from_report(report, out)
        return FileResponse(path, filename="live_top10.xlsx")

    out = _require_completed(task_id)
    try:
        report = jobs.get_report(task_id)
    except FileNotFoundError:
        raise HTTPException(404, "Отчёт не найден") from None
    path = build_top10_excel_from_report(report, out)
    return FileResponse(path, filename="report_top10.xlsx")


@router.post(
    "/reports/district/pdf",
    summary="PDF-отчёт по переданным данным (demo / без task_id)",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def post_district_report_pdf(data: DistrictReport):
    return _district_report_pdf_response(data)


@router.get(
    "/jobs/{task_id}/report.pdf",
    summary="Сводный PDF по всем муниципалитетам задачи",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def get_region_report_pdf(task_id: str):
    report = _get_task_report(task_id)

    districts = _collect_district_reports(report, task_id)
    if not districts:
        raise HTTPException(404, "Нет данных по муниципалитетам")

    try:
        pdf_bytes = build_region_pdf(
            districts,
            executive_summary=report.get("summary_text", ""),
            report=report,
        )
    except Exception as exc:
        raise HTTPException(500, f"Не удалось сформировать PDF: {exc}") from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition_region_header()},
    )


@router.post(
    "/reports/region/pdf",
    summary="Сводный PDF по списку муниципалитетов (demo)",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def post_region_report_pdf(body: RegionPdfRequest):
    if not body.districts:
        raise HTTPException(400, "Список муниципалитетов пуст")
    try:
        pdf_bytes = build_region_pdf(body.districts, executive_summary=body.executive_summary)
    except Exception as exc:
        raise HTTPException(500, f"Не удалось сформировать PDF: {exc}") from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition_region_header()},
    )


@router.get(
    "/jobs/{task_id}/reports/departments/preview",
    response_model=DepartmentReportsPreview,
    summary="Превью структуры отчётов для ведомств",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def get_department_reports_preview(task_id: str):
    labeled_df = _load_labeled_for_export(task_id)
    try:
        return build_department_preview(labeled_df)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post(
    "/jobs/{task_id}/reports/departments/generate",
    response_model=DepartmentReportsStatus,
    summary="Запуск фоновой генерации ZIP для ведомств",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def start_department_reports_generate(task_id: str, background_tasks: BackgroundTasks):
    labeled_df = _load_labeled_for_export(task_id)
    try:
        preview = build_department_preview(labeled_df)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    gen_task_id = f"dept-{uuid.uuid4().hex[:10]}"
    _department_export_tasks[gen_task_id] = {
        "task_id": gen_task_id,
        "parent_task_id": task_id,
        "status": "processing",
        "message": "Подготовка архива…",
        "progress": 0.0,
        "current": 0,
        "total": preview["reports_count"],
        "current_municipality": None,
        "current_agency": None,
        "phase": "start",
        "preview": preview,
        "zip_bytes": None,
        "error": None,
    }

    def _on_progress(current: int, total: int, municipality: str, agency: str, phase: str) -> None:
        task = _department_export_tasks.get(gen_task_id)
        if not task:
            return
        pct = round(100 * current / max(total, 1), 1)
        phase_labels = {
            "pdf": "Формирование PDF",
            "excel": "Формирование Excel",
            "archive": "Сборка архива",
        }
        task.update(
            {
                "current": current,
                "total": total,
                "progress": pct,
                "current_municipality": municipality or None,
                "current_agency": agency or None,
                "phase": phase,
                "message": (
                    f"{phase_labels.get(phase, 'Обработка')}: {municipality} → {agency}"
                    if municipality and agency
                    else "Финализация архива…"
                ),
            }
        )

    def _run() -> None:
        try:
            zip_bytes = build_department_reports_zip(labeled_df, on_progress=_on_progress)
            task = _department_export_tasks[gen_task_id]
            task["status"] = "completed"
            task["progress"] = 100.0
            task["message"] = "Архив готов к скачиванию"
            task["zip_bytes"] = zip_bytes
            task["phase"] = "done"
        except Exception as exc:
            task = _department_export_tasks.get(gen_task_id)
            if task:
                task["status"] = "failed"
                task["message"] = str(exc)
                task["error"] = str(exc)

    background_tasks.add_task(_run)
    return _department_status_response(gen_task_id)


def _department_status_response(gen_task_id: str) -> DepartmentReportsStatus:
    task = _department_export_tasks.get(gen_task_id)
    if not task:
        raise HTTPException(404, "Задача генерации не найдена")
    preview = task.get("preview")
    return DepartmentReportsStatus(
        task_id=gen_task_id,
        status=task["status"],
        message=task.get("message", ""),
        progress=float(task.get("progress") or 0),
        current=int(task.get("current") or 0),
        total=int(task.get("total") or 0),
        current_municipality=task.get("current_municipality"),
        current_agency=task.get("current_agency"),
        phase=task.get("phase"),
        preview=DepartmentReportsPreview(**preview) if preview else None,
    )


@router.get(
    "/reports/departments/{gen_task_id}",
    response_model=DepartmentReportsStatus,
    summary="Статус генерации ZIP для ведомств",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def get_department_reports_status(gen_task_id: str):
    return _department_status_response(gen_task_id)


@router.get(
    "/reports/departments/{gen_task_id}/download",
    summary="Скачать сформированный ZIP для ведомств",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def download_department_reports(gen_task_id: str):
    task = _department_export_tasks.get(gen_task_id)
    if not task:
        raise HTTPException(404, "Задача генерации не найдена")
    if task["status"] != "completed" or not task.get("zip_bytes"):
        raise HTTPException(409, f"Статус: {task['status']}")
    return _department_zip_response(task["zip_bytes"])


@router.get(
    "/jobs/{task_id}/reports/departments.zip",
    summary="ZIP-архив отчётов для ведомств (синхронно)",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def get_department_reports_zip(task_id: str):
    labeled_df = _load_labeled_for_export(task_id)
    try:
        zip_bytes = build_department_reports_zip(labeled_df)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Не удалось сформировать архив: {exc}") from exc
    return _department_zip_response(zip_bytes)


@router.get(
    "/jobs/{task_id}/reports/departments",
    summary="ZIP-архив отчётов для ведомств (синхронно, без .zip в URL)",
)
async def get_department_reports_zip_alt(task_id: str):
    return await get_department_reports_zip(task_id)


@router.post(
    "/reports/generate",
    response_model=GenerateReportResponse,
    summary="Генерация подробного LLM-отчёта по району",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def generate_district_report(
    request: GenerateReportRequest,
    background_tasks: BackgroundTasks,
    task_id: str | None = None,
    model: str | None = None,
):
    if not task_id:
        completed = [j for j in jobs.list_jobs() if j.get("status") == "completed"]
        if not completed:
            raise HTTPException(404, "Нет завершённых задач")
        completed.sort(key=lambda j: j.get("created_at") or "", reverse=True)
        task_id = completed[0]["task_id"]

    if not _is_live_task(task_id):
        try:
            jobs.require_completed(task_id)
        except KeyError:
            raise HTTPException(404, "Задача не найдена") from None
        except jobs.JobNotReadyError as exc:
            raise HTTPException(409, f"Статус: {exc.status}") from exc
    else:
        from src.routers._common import _ensure_live_task

        _ensure_live_task(task_id)

    gen_task_id = f"report-{uuid.uuid4().hex[:8]}"
    _district_tasks[gen_task_id] = {
        "task_id": gen_task_id,
        "status": "processing",
        "message": "Генерация отчёта…",
        "district_id": request.district_id,
        "parent_task_id": task_id,
    }

    def _run():
        try:
            start = request.start_date.isoformat() if request.start_date else None
            end = request.end_date.isoformat() if request.end_date else None
            jobs.generate_district_report(
                task_id,
                request.district_id,
                start_date=start,
                end_date=end,
                model=model,
            )
            _district_tasks[gen_task_id]["status"] = "completed"
            _district_tasks[gen_task_id]["message"] = "Отчёт готов"
        except Exception as exc:
            _district_tasks[gen_task_id]["status"] = "failed"
            _district_tasks[gen_task_id]["message"] = str(exc)

    background_tasks.add_task(_run)
    return GenerateReportResponse(
        task_id=gen_task_id,
        status="processing",
        message="Отчёт генерируется, проверьте /districts/{id}/report после завершения",
    )


@router.get(
    "/reports/generate/{gen_task_id}",
    response_model=GenerateReportResponse,
    summary="Статус генерации отчёта по району",
    dependencies=[Depends(require_permission(Permission.REPORTS))],
)
async def get_generate_status(gen_task_id: str):
    task = _district_tasks.get(gen_task_id)
    if not task:
        raise HTTPException(404, "Задача генерации не найдена")
    return GenerateReportResponse(
        task_id=gen_task_id,
        status=task["status"],
        message=task.get("message", ""),
    )


@router.post(
    "/operator/compose-email",
    response_model=ComposeEmailResponse,
    summary="LLM-генерация письма в ведомство по пакету обращений",
    dependencies=[Depends(require_permission(Permission.OPERATOR_EMAIL))],
)
async def compose_operator_email_api(request: ComposeEmailRequest):
    from app.config.llm import OLLAMA_MODEL
    from app.config.settings import PipelineSettings
    from app.summary import compose_operator_email as _compose

    cfg = PipelineSettings(
        input_path=DATA_DIR / "input.xlsx",
        ollama_model=request.model or OLLAMA_MODEL,
    )
    incidents = [i.model_dump() for i in request.incidents]
    result = _compose(incidents, request.agency_name, cfg, bundle_label=request.bundle_label)
    return ComposeEmailResponse(
        subject=result["subject"],
        body=result["body"],
        agency_name=request.agency_name,
        agency_email=request.agency_email,
    )
