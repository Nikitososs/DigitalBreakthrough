from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.paths import DATA_DIR, JOBS_DIR
from app.db import init_db
from src import jobs
from src.routers import (
    archive,
    auth,
    dashboard,
    incidents,
    jobs as jobs_router,
    live,
    reports,
    system,
    users,
)


def _init_database() -> None:
    import os
    import time

    retries = int(os.environ.get("DB_INIT_RETRIES", "15"))
    delay = float(os.environ.get("DB_INIT_DELAY_SEC", "2"))
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            init_db()
            db_url = os.environ.get("DATABASE_URL", "sqlite")
            print(f"ZeroProblems: БД готова ({db_url.split('@')[-1] if '@' in db_url else db_url})", flush=True)
            return
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                print(f"ZeroProblems: ожидание БД ({attempt}/{retries})…", flush=True)
                time.sleep(delay)
    if last_exc:
        raise last_exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    jobs.load_jobs_from_disk()
    _init_database()
    try:
        import onnxruntime as ort

        print(f"ZeroProblems: ONNX providers = {ort.get_available_providers()}", flush=True)
        from app.classify_service import _load_runtime

        _load_runtime()
    except Exception as exc:
        print(f"ZeroProblems: ONNX warmup failed: {exc}", flush=True)
    print("ZeroProblems: бэкенд запущен, ONNX + пайплайн готовы.", flush=True)
    yield
    print("Выключение бэкенда...")


app = FastAPI(
    title="ZeroProblems - ML API",
    description="ZeroProblems: анализ обращений граждан — ONNX-классификация, Top-10/Top-3, LLM-справки",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(live.public_router)
api_router.include_router(archive.public_router)
api_router.include_router(users.router)
api_router.include_router(live.router)
api_router.include_router(archive.router)
api_router.include_router(incidents.router)
api_router.include_router(jobs_router.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)

app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
