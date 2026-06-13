"""Сводка отчётов ведомств."""

import pandas as pd

from app.agency_mapping import resolve_agency_email, resolve_municipality_admin
from app.agency_pdf import build_agency_pdf, contact_summary_rows
from app.agency_report import _build_context, _summary_sheet_rows, AgencyWorkItem
from app.agency_summary import priority_level, top_topics_stats


def test_priority_critical():
    assert priority_level({4: 3, 3: 0, 2: 1, 1: 0}) == "КРИТИЧЕСКИЙ"


def test_build_context_smoke():
    df = pd.DataFrame(
        {
            "муниципалитет": ["Тестовый район"] * 5,
            "группа": ["ЖКХ"] * 5,
            "тема": ["Вода", "Вода", "Отопление", "Вода", "Канализация"],
            "текст": [
                "Нет воды третий день в доме по улице Ленина",
                "Отсутствует холодная вода во всём подъезде",
                "Не работает отопление в квартире",
                "Прорвало трубу во дворе многоквартирного дома",
                "Засор канализации подвал затоплен",
            ],
            "severity": [4, 3, 3, 2, 1],
            "дата_создания": ["2024-01-01"] * 5,
            "row_id": range(5),
        }
    )
    item = AgencyWorkItem(municipality="Тестовый район", agency="МинЖКХ", agency_df=df)
    ctx = _build_context(item, period_start_s="01.01.2024", period_end_s="31.01.2024")
    assert ctx.total == 5
    assert ctx.critical_total == 3
    assert ctx.top_topics
    assert ctx.recommendations
    assert len(top_topics_stats(df)) >= 2
    pdf = build_agency_pdf(ctx)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 8_000


def test_build_context_includes_contacts():
    agency = "Министерство жилищно-коммунального хозяйства и энергетики Омской области"
    muni = "г. Омск"
    df = pd.DataFrame(
        {
            "муниципалитет": [muni],
            "группа": ["ЖКХ"],
            "тема": ["Вода"],
            "текст": ["Нет воды третий день в доме по улице Ленина"],
            "severity": [3],
            "дата_создания": ["2024-01-01"],
            "row_id": [0],
        }
    )
    item = AgencyWorkItem(municipality=muni, agency=agency, agency_df=df)
    ctx = _build_context(item, period_start_s="01.01.2024", period_end_s="31.01.2024")

    admin = resolve_municipality_admin(muni)
    assert ctx.contact_email == resolve_agency_email(agency)
    assert ctx.admin_contact_name == admin["administration"]
    assert ctx.admin_contact_email == admin["email"]
    assert ctx.admin_contact_phone == admin["phone"]

    contact_rows = contact_summary_rows(ctx)
    labels = [label for label, _ in contact_rows]
    assert "Email ведомства" in labels
    assert "Администрация МО" in labels
    assert "Email МО" in labels

    summary = _summary_sheet_rows(ctx)
    summary_labels = summary["Показатель"].tolist()
    assert "Email ведомства" in summary_labels
    assert "Email МО" in summary_labels
