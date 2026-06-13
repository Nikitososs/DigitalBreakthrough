"""SQLAlchemy engine и сессии."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "zeroproblems.db"
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{DEFAULT_DB_PATH.as_posix()}",
)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _migrate_existing_schema(eng) -> None:
    """Добавляет новые колонки в существующую SQLite/Postgres БД без Alembic."""
    from sqlalchemy import inspect, text

    inspector = inspect(eng)
    if "stored_incidents" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("stored_incidents")}
    bool_default = "FALSE" if eng.dialect.name == "postgresql" else "0"
    additions = {
        "incident_number": "VARCHAR(32)",
        "closed_at": "TEXT",
        "workflow_step": "TEXT",
        "outcome": "TEXT",
        "manually_resolved": f"BOOLEAN DEFAULT {bool_default}",
        "is_resolved": f"BOOLEAN DEFAULT {bool_default}",
        "resolved_at": "TEXT",
        "resolved_note": "TEXT",
    }
    with eng.begin() as conn:
        for col, coltype in additions.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE stored_incidents ADD COLUMN {col} {coltype}"))

    if "is_resolved" not in existing:
        from app.db.repository import backfill_is_resolved_column

        backfill_is_resolved_column(eng)
        with eng.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_incidents_task_is_resolved "
                    "ON stored_incidents (task_id, is_resolved, severity)"
                )
            )

    if "stored_jobs" not in inspector.get_table_names():
        return
    job_cols = {c["name"] for c in inspector.get_columns("stored_jobs")}
    job_bool_default = "FALSE" if eng.dialect.name == "postgresql" else "0"
    job_additions = {
        "content_hash": "VARCHAR(64)",
        "is_duplicate": f"BOOLEAN DEFAULT {job_bool_default}",
        "duplicate_of_task_id": "VARCHAR(16)",
    }
    with eng.begin() as conn:
        for col, coltype in job_additions.items():
            if col not in job_cols:
                conn.execute(text(f"ALTER TABLE stored_jobs ADD COLUMN {col} {coltype}"))


def init_db() -> None:
    import os

    from app.db.models import Base

    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate_existing_schema(engine)

    from app.db.user_repo import ensure_admin_user

    ensure_admin_user(
        os.environ.get("ADMIN_USERNAME", "admin").strip(),
        os.environ.get("ADMIN_PASSWORD", "").strip(),
    )
    try:
        from app.db.user_repo import migrate_legacy_user_roles

        with get_session() as session:
            migrated = migrate_legacy_user_roles(session)
            if migrated:
                print(f"ZeroProblems: миграция ролей emergency→analyst: {migrated} пользов.", flush=True)
    except Exception:
        pass
    try:
        from app.config.paths import DATA_DIR
        from app.db.geocode_cache_repo import import_json_cache_file

        imported = import_json_cache_file(DATA_DIR / "geocode_cache.json")
        if imported:
            print(f"ZeroProblems: импортировано {imported} геокодов из JSON в таблицу geocode_cache", flush=True)
    except Exception:
        pass


@contextmanager
def get_session():
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
