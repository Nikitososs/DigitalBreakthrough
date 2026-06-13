"""Список обращений задачи для оператора / экстренного режима."""

from pathlib import Path

import pandas as pd
import pytest

from app.io import parquet_safe, select_labeled_columns
from app.task_incidents import list_incident_facets, list_task_incident_packages, list_task_incidents


def _write_labeled_parquet(path: Path, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    safe = parquet_safe(select_labeled_columns(df))
    path.parent.mkdir(parents=True, exist_ok=True)
    safe.to_parquet(path, index=False)


@pytest.fixture
def incidents_job(tmp_path: Path) -> tuple[str, Path]:
    task_id = "test-incidents-job"
    rows = [
        {
            "row_id": "r1",
            "дата_создания": "01.01.2024",
            "муниципалитет": "Омск г.о.",
            "населенный_пункт": "г. Омск",
            "улица": "Пригородная",
            "дом": "23к2",
            "текст": "Прорыв трубы на улице Ленина, вода заливает подъезд",
            "группа": "ЖКХ",
            "тема": "Водоснабжение",
            "severity": 4,
            "is_problem": True,
        },
        {
            "row_id": "r2",
            "дата_создания": "02.01.2024",
            "муниципалитет": "Омский м.р.",
            "текст": "Отсутствует отопление в детском саду уже третий день",
            "группа": "ЖКХ",
            "тема": "Отопление",
            "severity": 3,
            "is_problem": True,
        },
        {
            "row_id": "r3",
            "дата_создания": "03.01.2024",
            "муниципалитет": "Омск г.о.",
            "текст": "Шум от ремонта дороги в ночное время",
            "группа": "Дороги",
            "тема": "Ремонт",
            "severity": 1,
            "is_problem": True,
        },
        {
            "row_id": "r4",
            "дата_создания": "04.01.2024",
            "муниципалитет": "Омск г.о.",
            "текст": "Проблема с водоснабжением уже закрыта, вода подаётся в штатном режиме",
            "группа": "ЖКХ",
            "тема": "Водоснабжение",
            "severity": 3,
            "is_problem": True,
            "итог": "Решено",
        },
        {
            "row_id": "r5",
            "дата_создания": "05.01.2024",
            "муниципалитет": "Омский м.р.",
            "текст": "Отмечено решённым вручную, проблема устранена полностью",
            "группа": "ЖКХ",
            "тема": "Отопление",
            "severity": 2,
            "is_problem": True,
            "итог": "Разъяснено",
        },
    ]
    parquet_path = tmp_path / task_id / "cache" / "labeled.parquet"
    _write_labeled_parquet(parquet_path, rows)
    return task_id, tmp_path


def test_list_task_incidents_filters_severity(incidents_job):
    task_id, jobs_dir = incidents_job
    payload = list_task_incidents(task_id, jobs_dir, severity_min=3, severity_max=4)
    assert payload["total"] == 3
    assert len(payload["items"]) == 3
    assert {item["id"] for item in payload["items"]} == {"r1", "r2", "r4"}
    assert all(item["severity"] >= 3 for item in payload["items"])


def test_list_task_incidents_includes_contacts(incidents_job):
    task_id, jobs_dir = incidents_job
    item = list_task_incidents(task_id, jobs_dir, severity_min=4, severity_max=4)["items"][0]
    assert item["id"] == "r1"
    assert item["municipality"] == "Омск г.о."
    assert item["street"] == "Пригородная"
    assert item["has_address"] is True
    assert "Пригородная" in item["address"]
    assert item["agency"]
    assert item["municipality_admin"]


def test_list_task_incidents_group_and_search_filters(incidents_job):
    task_id, jobs_dir = incidents_job
    by_group = list_task_incidents(task_id, jobs_dir, group="ЖКХ")
    assert by_group["total"] == 4
    assert {item["id"] for item in by_group["items"]} == {"r1", "r2", "r4", "r5"}
    by_search = list_task_incidents(task_id, jobs_dir, search="отоплен")
    assert by_search["total"] == 2
    assert {item["id"] for item in by_search["items"]} == {"r2", "r5"}


def test_list_task_incidents_municipality_filter(incidents_job):
    task_id, jobs_dir = incidents_job
    payload = list_task_incidents(
        task_id,
        jobs_dir,
        severity_min=1,
        severity_max=4,
        municipality="Омский м.р.",
    )
    assert payload["total"] == 2
    assert {item["id"] for item in payload["items"]} == {"r2", "r5"}


def test_list_task_incidents_date_filter(incidents_job):
    task_id, jobs_dir = incidents_job
    payload = list_task_incidents(
        task_id,
        jobs_dir,
        severity_min=1,
        severity_max=4,
        created_from="2024-01-02",
        created_to="2024-01-02",
    )
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == "r2"


def test_list_incident_facets(incidents_job):
    task_id, jobs_dir = incidents_job
    facets = list_incident_facets(task_id, jobs_dir)
    assert facets["total"] == 4
    assert "ЖКХ" in facets["groups"]
    assert facets["with_address"] >= 1


def test_list_task_incidents_resolved_filter(incidents_job):
    task_id, jobs_dir = incidents_job
    resolved = list_task_incidents(
        task_id,
        jobs_dir,
        severity_min=1,
        severity_max=4,
        resolved=True,
    )
    assert resolved["total"] == 2
    assert {item["id"] for item in resolved["items"]} == {"r4", "r5"}

    open_only = list_task_incidents(
        task_id,
        jobs_dir,
        severity_min=1,
        severity_max=4,
        resolved=False,
    )
    assert open_only["total"] == 2
    assert {item["id"] for item in open_only["items"]} == {"r1", "r2"}


def test_list_task_incident_packages(incidents_job):
    task_id, jobs_dir = incidents_job
    payload = list_task_incident_packages(
        task_id,
        jobs_dir,
        severity_min=1,
        severity_max=4,
        resolved=False,
    )
    assert payload["total"] == 2
    assert len(payload["packages"]) >= 1
    bundle_items = [
        item["id"]
        for pkg in payload["packages"]
        for bundle in pkg["bundles"]
        for item in bundle["items"]
    ]
    assert set(bundle_items) == {"r1", "r2"}
