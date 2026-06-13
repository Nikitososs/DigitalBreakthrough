"""Сохранение результатов пайплайна в БД."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.db.repository import (
    dataframe_to_incident_rows,
    find_canonical_job_for_upload,
    has_stored_job,
    register_duplicate_stored_job,
    register_stored_job,
    upsert_job_and_incidents,
)
from app.db.session import get_session
from app.file_fingerprint import find_job_input_file, sha256_file
from app.io import read_labeled_parquet
from app.report import load_report_json


@dataclass
class PersistTaskResult:
    incident_count: int
    is_duplicate: bool = False
    duplicate_of_task_id: str | None = None


def _jobs_dir() -> Path:
    from app.config import paths

    return paths.JOBS_DIR


def _task_content_hash(task_id: str) -> str | None:
    job_dir = _jobs_dir() / task_id
    input_path = find_job_input_file(job_dir)
    if input_path is None:
        return None
    return sha256_file(input_path)


def persist_task_to_db(
    task_id: str,
    *,
    filename: str,
    created_at: str,
    rows_total: int,
    problem_count: int | None,
    municipality_count: int | None,
    labeled_parquet: Path,
    report_json_path: Path,
) -> PersistTaskResult:
    """Записывает задачу и строки labeled.parquet в БД. Дубликаты файла — только метаданные."""
    if not labeled_parquet.is_file():
        raise FileNotFoundError(f"Нет {labeled_parquet}")
    if not report_json_path.is_file():
        raise FileNotFoundError(f"Нет {report_json_path}")

    df = read_labeled_parquet(labeled_parquet)
    report = load_report_json(report_json_path)
    content_hash = _task_content_hash(task_id)

    with get_session() as session:
        canonical = find_canonical_job_for_upload(session, content_hash, exclude_task_id=task_id)
        if canonical is not None and content_hash:
            register_duplicate_stored_job(
                session,
                task_id=task_id,
                filename=filename,
                created_at=created_at,
                rows_total=rows_total,
                problem_count=problem_count,
                municipality_count=municipality_count,
                report=report,
                content_hash=content_hash,
                duplicate_of_task_id=canonical.task_id,
            )
            return PersistTaskResult(
                incident_count=0,
                is_duplicate=True,
                duplicate_of_task_id=canonical.task_id,
            )

        incidents = dataframe_to_incident_rows(df, session=session)
        for item in incidents:
            item["task_id"] = task_id
        upsert_job_and_incidents(
            session,
            task_id=task_id,
            filename=filename,
            created_at=created_at,
            rows_total=rows_total,
            problem_count=problem_count,
            municipality_count=municipality_count,
            report=report,
            incidents=incidents,
            content_hash=content_hash,
        )
    return PersistTaskResult(incident_count=len(incidents))


def register_task_from_disk(task_id: str, jobs_dir: Path) -> None:
    """Создаёт запись задачи в БД без импорта всех строк (для citizen/live)."""
    if has_stored_job(task_id):
        return
    job_dir = jobs_dir / task_id
    status_path = job_dir / "job_status.json"
    if not status_path.is_file():
        raise FileNotFoundError("Задача не найдена на диске")
    meta = json.loads(status_path.read_text(encoding="utf-8"))
    if meta.get("status") != "completed":
        raise ValueError("Задача ещё не завершена")

    stats = meta.get("stats") or {}
    report: dict = {}
    report_path = job_dir / "output" / "report.json"
    if report_path.is_file():
        report = load_report_json(report_path)

    with get_session() as session:
        register_stored_job(
            session,
            task_id=task_id,
            filename=str(meta.get("filename") or "dataset.xlsx"),
            created_at=str(meta.get("created_at") or ""),
            rows_total=int(meta.get("rows_processed") or stats.get("rows_processed") or 0),
            problem_count=stats.get("problem_count"),
            municipality_count=stats.get("municipality_count"),
            report=report,
            content_hash=meta.get("content_hash") or _task_content_hash(task_id),
        )


def import_task_from_disk(task_id: str, jobs_dir: Path) -> PersistTaskResult:
    """Импорт завершённой задачи из cache/jobs в БД."""
    job_dir = jobs_dir / task_id
    status_path = job_dir / "job_status.json"
    if not status_path.is_file():
        raise FileNotFoundError("Задача не найдена на диске")
    meta = json.loads(status_path.read_text(encoding="utf-8"))
    if meta.get("status") != "completed":
        raise ValueError("Задача ещё не завершена")

    stats = meta.get("stats") or {}
    return persist_task_to_db(
        task_id,
        filename=str(meta.get("filename") or "dataset.xlsx"),
        created_at=str(meta.get("created_at") or ""),
        rows_total=int(meta.get("rows_processed") or stats.get("rows_processed") or 0),
        problem_count=stats.get("problem_count"),
        municipality_count=stats.get("municipality_count"),
        labeled_parquet=job_dir / "cache" / "labeled.parquet",
        report_json_path=job_dir / "output" / "report.json",
    )
