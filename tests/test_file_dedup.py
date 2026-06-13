"""Дедупликация загрузок по SHA-256 содержимого Excel."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, IncidentRegistry, StoredIncident, StoredJob
from app.db.repository import find_canonical_job_by_hash, has_incidents_in_db, lookup_registry_resolved
from app.db.session import get_session
from app.file_fingerprint import sha256_file
from app.incident_store import persist_task_to_db
from app.io import parquet_safe, select_labeled_columns


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "dedup.db"
    test_engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=test_engine)
    monkeypatch.setattr("app.db.session.engine", test_engine)
    monkeypatch.setattr("app.db.session.SessionLocal", TestSession)
    yield


def _write_labeled_parquet(path: Path, rows: list[dict]) -> None:
    df = parquet_safe(select_labeled_columns(pd.DataFrame(rows)))
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _write_task(task_dir: Path, task_id: str, *, rows: list[dict], file_bytes: bytes) -> None:
    task_dir.mkdir(parents=True)
    (task_dir / "input.xlsx").write_bytes(file_bytes)
    _write_labeled_parquet(task_dir / "cache" / "labeled.parquet", rows)
    out = task_dir / "output"
    out.mkdir()
    (out / "report.json").write_text(json.dumps({"districts": []}, ensure_ascii=False), encoding="utf-8")


def test_sha256_same_content_same_hash(tmp_path):
    p1 = tmp_path / "a.xlsx"
    p2 = tmp_path / "b.xlsx"
    data = b"same excel bytes"
    p1.write_bytes(data)
    p2.write_bytes(data)
    assert sha256_file(p1) == sha256_file(p2)


def test_persist_skips_incidents_for_duplicate_file(isolated_db, tmp_path, monkeypatch):
    from app.config import paths

    jobs_root = tmp_path / "jobs"
    monkeypatch.setattr(paths, "JOBS_DIR", jobs_root)

    file_bytes = b"duplicate-dataset-content"
    rows = [
        {
            "row_id": "1001",
            "id_обращения": "1001",
            "дата_создания": "01.01.2024",
            "текст": "a",
            "severity": 2,
            "is_problem": True,
            "муниципалитет": "г. Омск",
            "группа": "ЖКХ",
            "тема": "вода",
        }
    ]

    task_a = jobs_root / "aaaaaaaa"
    _write_task(task_a, "aaaaaaaa", rows=rows, file_bytes=file_bytes)

    first = persist_task_to_db(
        "aaaaaaaa",
        filename="test.xlsx",
        created_at="2026-01-01T00:00:00Z",
        rows_total=1,
        problem_count=1,
        municipality_count=1,
        labeled_parquet=task_a / "cache" / "labeled.parquet",
        report_json_path=task_a / "output" / "report.json",
    )
    assert first.incident_count == 1
    assert first.is_duplicate is False
    assert has_incidents_in_db("aaaaaaaa")

    task_b = jobs_root / "bbbbbbbb"
    _write_task(task_b, "bbbbbbbb", rows=rows, file_bytes=file_bytes)

    second = persist_task_to_db(
        "bbbbbbbb",
        filename="test.xlsx",
        created_at="2026-01-02T00:00:00Z",
        rows_total=1,
        problem_count=1,
        municipality_count=1,
        labeled_parquet=task_b / "cache" / "labeled.parquet",
        report_json_path=task_b / "output" / "report.json",
    )
    assert second.is_duplicate is True
    assert second.duplicate_of_task_id == "aaaaaaaa"
    assert second.incident_count == 0
    assert not has_incidents_in_db("bbbbbbbb")

    with get_session() as session:
        dup_job = session.get(StoredJob, "bbbbbbbb")
        assert dup_job is not None
        assert dup_job.is_duplicate is True
        canonical = find_canonical_job_by_hash(session, dup_job.content_hash)
        assert canonical is not None
        assert canonical.task_id == "aaaaaaaa"
        dup_count = session.scalar(
            select(func.count()).select_from(StoredIncident).where(StoredIncident.task_id == "bbbbbbbb")
        )
        assert int(dup_count or 0) == 0


def test_find_canonical_backfills_legacy_job_hash(isolated_db, tmp_path, monkeypatch):
    from app.config import paths
    from app.db.repository import backfill_stored_job_hashes, find_canonical_job_for_upload
    from app.db.session import get_session

    jobs_root = tmp_path / "jobs"
    monkeypatch.setattr(paths, "JOBS_DIR", jobs_root)

    file_bytes = b"legacy-then-duplicate"
    rows = [
        {
            "row_id": "1001",
            "id_обращения": "1001",
            "дата_создания": "01.01.2024",
            "текст": "a",
            "severity": 2,
            "is_problem": True,
            "муниципалитет": "г. Омск",
            "группа": "ЖКХ",
            "тема": "вода",
        }
    ]

    task_a = jobs_root / "aaaaaaaa"
    _write_task(task_a, "aaaaaaaa", rows=rows, file_bytes=file_bytes)
    persist_task_to_db(
        "aaaaaaaa",
        filename="test.xlsx",
        created_at="2026-01-01T00:00:00Z",
        rows_total=1,
        problem_count=1,
        municipality_count=1,
        labeled_parquet=task_a / "cache" / "labeled.parquet",
        report_json_path=task_a / "output" / "report.json",
    )

    with get_session() as session:
        legacy = session.get(__import__("app.db.models", fromlist=["StoredJob"]).StoredJob, "aaaaaaaa")
        legacy.content_hash = None
        session.flush()

    task_b = jobs_root / "bbbbbbbb"
    _write_task(task_b, "bbbbbbbb", rows=rows, file_bytes=file_bytes)
    second = persist_task_to_db(
        "bbbbbbbb",
        filename="test.xlsx",
        created_at="2026-01-02T00:00:00Z",
        rows_total=1,
        problem_count=1,
        municipality_count=1,
        labeled_parquet=task_b / "cache" / "labeled.parquet",
        report_json_path=task_b / "output" / "report.json",
    )
    assert second.is_duplicate is True
    assert second.duplicate_of_task_id == "aaaaaaaa"


def test_reconcile_demotes_existing_duplicates(isolated_db, tmp_path, monkeypatch):
    from app.config import paths
    from app.db.repository import _content_hash_from_disk, reconcile_duplicate_stored_jobs, upsert_job_and_incidents, dataframe_to_incident_rows
    from app.db.session import get_session
    from app.io import read_labeled_parquet
    from app.report import load_report_json

    jobs_root = tmp_path / "jobs"
    monkeypatch.setattr(paths, "JOBS_DIR", jobs_root)

    file_bytes = b"already-both-imported"
    rows = [
        {
            "row_id": "1001",
            "id_обращения": "1001",
            "дата_создания": "01.01.2024",
            "текст": "a",
            "severity": 2,
            "is_problem": True,
            "муниципалитет": "г. Омск",
            "группа": "ЖКХ",
            "тема": "вода",
        }
    ]

    task_a = jobs_root / "aaaaaaaa"
    task_b = jobs_root / "bbbbbbbb"
    _write_task(task_a, "aaaaaaaa", rows=rows, file_bytes=file_bytes)
    _write_task(task_b, "bbbbbbbb", rows=rows, file_bytes=file_bytes)

    persist_task_to_db(
        "aaaaaaaa",
        filename="test.xlsx",
        created_at="2026-01-01T00:00:00Z",
        rows_total=1,
        problem_count=1,
        municipality_count=1,
        labeled_parquet=task_a / "cache" / "labeled.parquet",
        report_json_path=task_a / "output" / "report.json",
    )
    content_hash = _content_hash_from_disk("aaaaaaaa")

    df = read_labeled_parquet(task_b / "cache" / "labeled.parquet")
    report = load_report_json(task_b / "output" / "report.json")
    with get_session() as session:
        incidents = dataframe_to_incident_rows(df, session=session)
        for item in incidents:
            item["task_id"] = "bbbbbbbb"
        upsert_job_and_incidents(
            session,
            task_id="bbbbbbbb",
            filename="test.xlsx",
            created_at="2026-01-02T00:00:00Z",
            rows_total=1,
            problem_count=1,
            municipality_count=1,
            report=report,
            incidents=incidents,
            content_hash=content_hash,
        )

    stats = reconcile_duplicate_stored_jobs()
    assert "bbbbbbbb" in stats["demoted"]

    with get_session() as session:
        from app.db.models import StoredJob

        original = session.get(StoredJob, "aaaaaaaa")
        dup = session.get(StoredJob, "bbbbbbbb")
        assert original is not None and not original.is_duplicate
        assert original.incident_count == 1
        assert dup is not None and dup.is_duplicate
        assert dup.duplicate_of_task_id == "aaaaaaaa"
        assert dup.incident_count == 0


def test_lookup_registry_resolved_batches_in_clause(isolated_db, monkeypatch):
    import app.db.repository as repo

    monkeypatch.setattr(repo, "REGISTRY_IN_CHUNK", 2)
    ids = [f"id-{i}" for i in range(5)]
    with get_session() as session:
        for ext in ids:
            session.add(
                IncidentRegistry(
                    external_id=ext,
                    manually_resolved=True,
                    first_task_id="t1",
                    last_task_id="t1",
                    updated_at="2026-01-01T00:00:00+00:00",
                )
            )
        session.flush()
        found = lookup_registry_resolved(session, ids)
    assert set(found) == set(ids)
