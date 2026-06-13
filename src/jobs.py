"""Управление фоновыми задачами: память + персистентность на диск."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config.llm import OLLAMA_MODEL
from app.config.paths import DATA_DIR, JOBS_DIR
from app.config.settings import PipelineSettings
from app.pipeline import run_pipeline
from app.progress import PIPELINE_STEPS, initial_steps, overall_progress
from app.report import load_report_json
from app.summary import build_district_report_summary
from schemas import PipelineOptions

_jobs: dict[str, dict] = {}
_progress_persist_ts: dict[str, float] = {}

_STALE_JOB_MESSAGE = "Прервано перезапуском сервера"
_PROGRESS_PERSIST_INTERVAL_SEC = 0.75
_TOMBSTONES_PATH = DATA_DIR / "cache_tombstones.json"
_TASK_ID_RE = re.compile(r"^[a-f0-9]{8}$")


def _valid_task_id(task_id: str) -> bool:
    return bool(_TASK_ID_RE.match(task_id))


def _load_tombstones() -> set[str]:
    if not _TOMBSTONES_PATH.is_file():
        return set()
    try:
        data = json.loads(_TOMBSTONES_PATH.read_text(encoding="utf-8"))
        return {str(x) for x in data if _valid_task_id(str(x))}
    except (json.JSONDecodeError, OSError):
        return set()


def _save_tombstones(ids: set[str]) -> None:
    _TOMBSTONES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _TOMBSTONES_PATH.write_text(
        json.dumps(sorted(ids), ensure_ascii=False, indent=0),
        encoding="utf-8",
    )


def _add_tombstone(task_id: str) -> None:
    ids = _load_tombstones()
    ids.add(task_id)
    _save_tombstones(ids)


def _remove_tombstone(task_id: str) -> None:
    ids = _load_tombstones()
    if task_id not in ids:
        return
    ids.discard(task_id)
    _save_tombstones(ids)


def is_cache_tombstoned(task_id: str) -> bool:
    return task_id in _load_tombstones()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _finalize_step_timing(step: dict) -> None:
    if step.get("ended_at"):
        return
    ended = datetime.now(timezone.utc)
    step["ended_at"] = ended.isoformat()
    started_at = step.get("started_at")
    if started_at and step.get("duration_sec") is None:
        started = datetime.fromisoformat(started_at)
        step["duration_sec"] = round((ended - started).total_seconds(), 1)


def job_path(task_id: str) -> Path:
    return JOBS_DIR / task_id


def output_dir(task_id: str) -> Path:
    return job_path(task_id) / "output"


def persist_job(task_id: str) -> None:
    if task_id not in _jobs:
        return
    path = job_path(task_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "job_status.json").write_text(
        json.dumps(_jobs[task_id], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _reconcile_job_on_load(job: dict) -> bool:
    """Помечает прерванные задачи и выравнивает шаги после сбоя."""
    changed = False
    status = job.get("status")
    if status in ("running", "queued"):
        job["status"] = "failed"
        job["message"] = _STALE_JOB_MESSAGE
        changed = True
    if job.get("status") == "failed":
        for step in job.get("steps") or []:
            if step.get("status") == "running":
                step["status"] = "error"
                if not step.get("detail"):
                    step["detail"] = job.get("message") or "ошибка"
                changed = True
    return changed


def load_jobs_from_disk() -> None:
    if not JOBS_DIR.exists():
        return
    for job_dir in sorted(JOBS_DIR.iterdir()):
        if not job_dir.is_dir():
            continue
        status_path = job_dir / "job_status.json"
        if not status_path.exists():
            continue
        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
            task_id = data.get("task_id") or job_dir.name
            if is_cache_tombstoned(task_id):
                continue
            if _reconcile_job_on_load(data):
                _jobs[task_id] = data
                persist_job(task_id)
            else:
                _jobs[task_id] = data
        except (json.JSONDecodeError, KeyError, OSError):
            continue


def normalize_job_steps(job: dict) -> list[dict]:
    """Всегда возвращает полный список шагов пайплайна (6 этапов)."""
    existing = {step["id"]: step for step in (job.get("steps") or [])}
    normalized: list[dict] = []
    for step_id, label in PIPELINE_STEPS:
        step = dict(existing.get(step_id, {}))
        step.setdefault("id", step_id)
        step.setdefault("label", label)
        step.setdefault("status", "pending")
        step.setdefault("detail", "")
        normalized.append(step)
    return normalized


def get_job(task_id: str) -> dict | None:
    job = _jobs.get(task_id)
    if job is None:
        return None
    job = dict(job)
    job["steps"] = normalize_job_steps(job)
    return job


def list_jobs() -> list[dict]:
    tombstones = _load_tombstones()
    return [j for j in _jobs.values() if j.get("task_id") not in tombstones]


def _rmtree_onerror(func, path, _exc_info):
    """chmod + retry (Docker/Windows volume часто блокирует read-only файлы)."""
    try:
        os.chmod(path, stat.S_IWUSR | stat.S_IREAD | stat.S_IXUSR)
        func(path)
    except OSError:
        if os.path.isdir(path):
            return
        try:
            os.chmod(path, 0o666)
            os.remove(path)
        except OSError:
            raise


def _remove_job_dir(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        shutil.rmtree(path, onerror=_rmtree_onerror)
    except OSError:
        pass
    if not path.exists():
        return True
    for item in sorted(path.rglob("*"), reverse=True):
        try:
            if item.is_file() or item.is_symlink():
                try:
                    item.chmod(0o666)
                except OSError:
                    pass
                item.unlink(missing_ok=True)
            elif item.is_dir():
                try:
                    item.chmod(0o777)
                except OSError:
                    pass
                try:
                    item.rmdir()
                except OSError:
                    pass
        except OSError:
            continue
    shutil.rmtree(path, ignore_errors=True)
    return not path.exists()


def delete_cached_job(task_id: str) -> bool:
    """Удаляет задачу из памяти и каталога cache/jobs (не трогает БД)."""
    if not _valid_task_id(task_id):
        return False
    path = job_path(task_id)
    in_memory = task_id in _jobs
    on_disk = path.exists()
    if not on_disk and not in_memory:
        return task_id in _load_tombstones()
    _jobs.pop(task_id, None)
    _progress_persist_ts.pop(task_id, None)
    if on_disk and not _remove_job_dir(path):
        _add_tombstone(task_id)
        return True
    _remove_tombstone(task_id)
    return True


def delete_cached_jobs(task_ids: list[str]) -> dict:
    deleted: list[str] = []
    missing: list[str] = []
    for task_id in task_ids:
        if delete_cached_job(task_id):
            deleted.append(task_id)
        else:
            missing.append(task_id)
    return {"deleted": deleted, "missing": missing, "count": len(deleted)}


def update_job_step(
    task_id: str,
    step_id: str,
    status: str,
    detail: str = "",
    *,
    step_fraction: float | None = None,
) -> None:
    steps = _jobs[task_id].get("steps") or initial_steps()
    order = [s[0] for s in PIPELINE_STEPS]
    if status == "running" and step_id in order:
        idx = order.index(step_id)
        for step in steps:
            if step["id"] in order[:idx] and step["status"] == "running":
                step["status"] = "done"
                step["progress"] = 100.0
                _finalize_step_timing(step)
    for step in steps:
        if step["id"] == step_id:
            step["status"] = status
            if detail:
                step["detail"] = detail
            elif status == "running" and not step.get("detail"):
                step["detail"] = "выполняется…"
            if status == "running" and not step.get("started_at"):
                step["started_at"] = _now_iso()
            if status in ("done", "error"):
                step["progress"] = 100.0
                _finalize_step_timing(step)
            elif step_fraction is not None:
                step["progress"] = round(max(0.0, min(100.0, step_fraction * 100)), 1)
            break
    _jobs[task_id]["steps"] = steps
    if status == "done":
        _jobs[task_id]["progress"] = overall_progress(step_id, step_done=True)
    elif step_fraction is not None:
        _jobs[task_id]["progress"] = round(
            overall_progress(step_id, step_fraction=step_fraction),
            1,
        )
    if detail:
        _jobs[task_id]["message"] = detail

    force_persist = status in ("done", "error") or step_fraction is None
    now = time.perf_counter()
    last = _progress_persist_ts.get(task_id, 0.0)
    if force_persist or now - last >= _PROGRESS_PERSIST_INTERVAL_SEC:
        _progress_persist_ts[task_id] = now
        persist_job(task_id)


def run_job(task_id: str, input_path: Path, options: PipelineOptions) -> None:
    out = output_dir(task_id)
    out.mkdir(parents=True, exist_ok=True)
    _jobs[task_id]["status"] = "running"
    _jobs[task_id]["steps"] = initial_steps()
    _jobs[task_id]["message"] = "Обработка…"
    persist_job(task_id)

    started = time.perf_counter()

    def on_progress(
        step_id: str,
        status: str,
        detail: str = "",
        step_fraction: float | None = None,
    ) -> None:
        update_job_step(task_id, step_id, status, detail, step_fraction=step_fraction)

    try:
        cfg = PipelineSettings(
            input_path=input_path,
            output_dir=out,
            cache_dir=job_path(task_id) / "cache",
            batch_size=options.batch_size,
            skip_summary=options.skip_summary,
            nrows=options.nrows,
            ollama_model=options.model or OLLAMA_MODEL,
            llm_fast_mode=options.llm_fast_mode,
        )
        result = run_pipeline(cfg, on_progress=on_progress)
        elapsed = round(time.perf_counter() - started, 1)
        stats = {
            "elapsed_sec": elapsed,
            "rows_processed": result.rows_processed,
            "problem_count": result.problem_count,
            "municipality_count": result.municipality_count,
            "report_file": result.report_path.name,
        }
        _jobs[task_id]["status"] = "completed"
        _jobs[task_id]["progress"] = 100.0
        _jobs[task_id]["rows_processed"] = result.rows_processed
        _jobs[task_id]["stats"] = stats
        _jobs[task_id]["message"] = (
            f"Готово за {elapsed} с · {result.rows_processed} строк · "
            f"{result.municipality_count} МО"
        )
        persist_job(task_id)
        try:
            from app.incident_store import persist_task_to_db

            job = _jobs[task_id]
            result = persist_task_to_db(
                task_id,
                filename=str(job.get("filename") or "dataset.xlsx"),
                created_at=str(job.get("created_at") or _now_iso()),
                rows_total=int(result.rows_processed),
                problem_count=stats.get("problem_count"),
                municipality_count=result.municipality_count,
                labeled_parquet=job_path(task_id) / "cache" / "labeled.parquet",
                report_json_path=output_dir(task_id) / "report.json",
            )
            if result.is_duplicate:
                print(
                    f"ZeroProblems: задача {task_id} — дубликат файла "
                    f"(оригинал {result.duplicate_of_task_id}), обращения не сохранены",
                    flush=True,
                )
            else:
                print(
                    f"ZeroProblems: задача {task_id} сохранена в БД ({result.incident_count} строк)",
                    flush=True,
                )
                try:
                    from app.geocode_worker import schedule_warmup_after_import

                    schedule_warmup_after_import(task_id)
                    print(f"ZeroProblems: фоновый прогрев геокодов для {task_id} запущен", flush=True)
                except Exception as geo_exc:
                    print(f"ZeroProblems: не удалось запустить прогрев геокодов: {geo_exc}", flush=True)
        except Exception as store_exc:
            print(f"ZeroProblems: не удалось сохранить в БД: {store_exc}", flush=True)
    except Exception as exc:
        _jobs[task_id]["status"] = "failed"
        _jobs[task_id]["message"] = str(exc)
        update_job_step(task_id, "report", "error", str(exc))
        persist_job(task_id)


def require_job(task_id: str) -> dict:
    job = get_job(task_id)
    if job is None:
        raise KeyError(task_id)
    return job


class JobNotReadyError(Exception):
    def __init__(self, status: str):
        self.status = status
        super().__init__(status)


def require_completed(task_id: str) -> Path:
    job = require_job(task_id)
    if job["status"] != "completed":
        raise JobNotReadyError(job["status"])
    return output_dir(task_id)


def get_report(task_id: str) -> dict:
    from app.live_stream import LIVE_STREAM_TASK_ID

    if task_id == LIVE_STREAM_TASK_ID:
        from app.live_report import build_live_report_from_db

        return build_live_report_from_db(task_id)

    try:
        out = require_completed(task_id)
        path = out / "report.json"
        if path.exists():
            return load_report_json(path)
    except (KeyError, JobNotReadyError, FileNotFoundError):
        pass

    from app.db.repository import get_stored_report

    stored = get_stored_report(task_id)
    if stored and stored.get("all") is not None:
        return stored
    raise FileNotFoundError("report.json")


def get_labeled_df(task_id: str):
    from app.live_report import load_task_incidents_df
    from app.live_stream import LIVE_STREAM_TASK_ID

    if task_id == LIVE_STREAM_TASK_ID:
        df = load_task_incidents_df(task_id)
        return df if not df.empty else None

    cache_path = job_path(task_id) / "cache" / "labeled.parquet"
    if cache_path.exists():
        from app.io import read_labeled_parquet

        df = read_labeled_parquet(cache_path)
        if not df.empty:
            return df

    df = load_task_incidents_df(task_id)
    return df if not df.empty else None


def generate_district_report(
    task_id: str,
    district_id: int,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    model: str | None = None,
) -> str:
    from app.live_stream import LIVE_STREAM_TASK_ID

    report = get_report(task_id)
    all_rows = report.get("all", [])
    target = next(
        (r for r in all_rows if int(r.get("district_id", r.get("rank", -1))) == district_id),
        None,
    )
    if target is None:
        raise ValueError(f"Район с id={district_id} не найден")

    if task_id == LIVE_STREAM_TASK_ID:
        from app.config.paths import DATA_DIR
        from app.live_report import load_task_incidents_df

        labeled = load_task_incidents_df(task_id)
        if labeled.empty:
            raise FileNotFoundError("Размеченные данные не найдены")
        live_out = DATA_DIR / "live_export"
        cfg = PipelineSettings(
            input_path=live_out / "input.xlsx",
            output_dir=live_out,
            cache_dir=live_out,
            ollama_model=model or OLLAMA_MODEL,
        )
        summary = build_district_report_summary(
            labeled,
            target["муниципалитет"],
            cfg,
            start_date=start_date,
            end_date=end_date,
        )
        district_reports = live_out / "district_reports"
        district_reports.mkdir(parents=True, exist_ok=True)
        report_path = district_reports / f"district_{district_id}.json"
        payload = {
            "district_id": district_id,
            "district_name": target["муниципалитет"],
            "analytical_summary": summary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    out = require_completed(task_id)
    cache_path = job_path(task_id) / "cache" / "labeled.parquet"
    if not cache_path.exists():
        raise FileNotFoundError("Размеченные данные не найдены")


    from app.io import read_labeled_parquet

    labeled = read_labeled_parquet(cache_path)
    cfg = PipelineSettings(
        input_path=out / "input.xlsx",
        output_dir=out,
        cache_dir=job_path(task_id) / "cache",
        ollama_model=model or OLLAMA_MODEL,
    )
    summary = build_district_report_summary(
        labeled,
        target["муниципалитет"],
        cfg,
        start_date=start_date,
        end_date=end_date,
    )

    district_reports = out / "district_reports"
    district_reports.mkdir(parents=True, exist_ok=True)
    report_path = district_reports / f"district_{district_id}.json"
    payload = {
        "district_id": district_id,
        "district_name": target["муниципалитет"],
        "analytical_summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def get_district_summary(task_id: str, district_id: int) -> str | None:
    from app.live_stream import LIVE_STREAM_TASK_ID

    if task_id == LIVE_STREAM_TASK_ID:
        from app.config.paths import DATA_DIR

        path = DATA_DIR / "live_export" / "district_reports" / f"district_{district_id}.json"
    else:
        path = output_dir(task_id) / "district_reports" / f"district_{district_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("analytical_summary")


def create_job(task_id: str, filename: str, *, content_hash: str | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    job = {
        "task_id": task_id,
        "status": "queued",
        "message": "В очереди",
        "created_at": now,
        "filename": filename,
        "rows_processed": None,
        "stats": None,
        "steps": initial_steps(),
        "progress": 0.0,
    }
    if content_hash:
        job["content_hash"] = content_hash
    _jobs[task_id] = job
    job_path(task_id).mkdir(parents=True, exist_ok=True)
    persist_job(task_id)
    return job
