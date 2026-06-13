"""Тесты сопоставления групп и муниципалитетов."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agency_mapping import (
    load_agency_mapping,
    load_municipality_mapping,
    resolve_agency,
    resolve_contact,
    resolve_municipality_admin,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "cache" / "jobs" / "75b39eb6" / "output" / "report.json"


def _groups_from_report() -> set[str]:
    if not REPORT_PATH.is_file():
        pytest.skip("report.json cache not available")
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    return {str(row["группа"]).strip() for row in report.get("groups", []) if row.get("группа")}


def _municipalities_from_report() -> set[str]:
    if not REPORT_PATH.is_file():
        pytest.skip("report.json cache not available")
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    names: set[str] = set()
    for key in ("all", "top3", "top10"):
        for row in report.get(key, []):
            name = str(row.get("муниципалитет", "")).strip()
            if name:
                names.add(name)
    return names


def test_all_report_groups_mapped() -> None:
    mapping = load_agency_mapping()["group_to_agency"]
    missing = sorted(g for g in _groups_from_report() if g not in mapping)
    assert missing == [], f"Unmapped groups: {missing}"


def test_resolve_agency_known_group() -> None:
    assert resolve_agency("ЖКХ") == (
        "Министерство жилищно-коммунального хозяйства и энергетики Омской области"
    )


def test_resolve_agency_new_groups() -> None:
    assert resolve_agency("Имущественные и земельные отношения") == (
        "Министерство имущественных отношений Омской области"
    )
    assert resolve_agency("Физическая культура и спорт") == "Министерство спорта Омской области"
    assert resolve_agency("ЦУР") == "Аппарат Губернатора и Правительства Омской области"


def test_municipality_alias_omsk() -> None:
    admin = resolve_municipality_admin("г. Омск")
    assert admin["municipality"] == "Омск г.о."
    assert admin["administration"] == "Администрация города Омска"
    assert admin["email"] == "mail@admomsk.ru"
    assert admin["contact_verified"] is True


def test_municipality_lookup_bolsherechensky() -> None:
    admin = resolve_municipality_admin("Большереченский район")
    assert "Большереченск" in str(admin["administration"])
    assert admin["email"] == "adm@bolr.omskportal.ru"
    assert admin["contact_verified"] is True


def test_all_report_municipalities_have_entry() -> None:
    municipalities = load_municipality_mapping()["municipalities"]
    missing = sorted(m for m in _municipalities_from_report() if m not in municipalities)
    assert missing == [], f"Municipalities without mapping: {missing}"


def test_resolve_contact_layers() -> None:
    contact = resolve_contact("Омский район", "Министерство транспорта и дорожного хозяйства Омской области")
    assert contact["agency_email"] == "mintrans@admomsk.ru"
    assert contact["municipality_admin"]["email"] == "oms@omsk.omskportal.ru"
