"""Единый live-поток обращений граждан в Postgres (без привязки к Excel-задаче)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.constants import LIVE_STREAM_TASK_ID
from app.db.repository import has_stored_job, register_stored_job
from app.db.session import get_session

__all__ = ["LIVE_STREAM_TASK_ID", "ensure_live_stream_job"]


def ensure_live_stream_job() -> str:
    """Создаёт служебную запись в stored_jobs, если её ещё нет."""
    if has_stored_job(LIVE_STREAM_TASK_ID):
        return LIVE_STREAM_TASK_ID
    now = datetime.now(timezone.utc).isoformat()
    with get_session() as session:
        register_stored_job(
            session,
            task_id=LIVE_STREAM_TASK_ID,
            filename="Live-поток граждан",
            created_at=now,
            rows_total=0,
            problem_count=0,
            municipality_count=0,
            report={},
        )
    return LIVE_STREAM_TASK_ID
