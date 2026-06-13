"""Импорт всех завершённых задач из cache/jobs в SQLite."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config.paths import JOBS_DIR
from app.db import init_db
from app.db.repository import has_stored_job
from app.incident_store import import_task_from_disk
from src import jobs


def main() -> None:
    init_db()
    jobs.load_jobs_from_disk()
    imported = 0
    skipped = 0
    for job in jobs.list_jobs():
        tid = job.get("task_id")
        if not tid or job.get("status") != "completed":
            continue
        if has_stored_job(tid):
            skipped += 1
            continue
        try:
            result = import_task_from_disk(tid, JOBS_DIR)
            label = "duplicate" if result.is_duplicate else f"{result.incident_count} rows"
            print(f"{tid}: {label}")
            imported += 1
        except Exception as exc:
            print(f"{tid}: ERROR {exc}")
    print(f"Done: imported {imported}, skipped {skipped}")


if __name__ == "__main__":
    main()
