"""Live-поток обращений граждан: submit и недавние события."""

from fastapi import APIRouter, Depends

from app.auth.deps import require_permission
from app.auth.permissions import Permission
from app.complaint_submit import recent_citizen_events
from app.live_stream import ensure_live_stream_job
from schemas import (
    LiveEventResponse,
    LiveRecentResponse,
    SubmitComplaintRequest,
    SubmitComplaintResponse,
)
from src.routers._common import _ensure_task_in_db, _submit_complaint_body

router = APIRouter()
public_router = APIRouter()


@public_router.post(
    "/complaints",
    response_model=SubmitComplaintResponse,
    summary="Подать обращение гражданина (единый live-поток в Postgres)",
)
async def submit_complaint_live(body: SubmitComplaintRequest):
    task_id = ensure_live_stream_job()
    return _submit_complaint_body(body, task_id)


@router.post(
    "/tasks/{task_id}/complaints",
    response_model=SubmitComplaintResponse,
    summary="Подать обращение к конкретной задаче (legacy)",
    dependencies=[Depends(require_permission(Permission.INCIDENTS_WRITE))],
)
async def submit_complaint(task_id: str, body: SubmitComplaintRequest):
    _ensure_task_in_db(task_id)
    return _submit_complaint_body(body, task_id)


@router.get(
    "/live/recent",
    response_model=LiveRecentResponse,
    summary="Новые обращения граждан с момента since",
    dependencies=[Depends(require_permission(Permission.LIVE_READ))],
)
async def live_recent(task_id: str | None = None, since: str | None = None, limit: int = 20):
    if task_id:
        _ensure_task_in_db(task_id)
    items = [LiveEventResponse(**e) for e in recent_citizen_events(task_id, since=since, limit=limit)]
    return LiveRecentResponse(items=items, count=len(items))
