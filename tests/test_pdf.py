"""PDF district and region reports."""

from datetime import datetime

from app.pdf_report import build_district_pdf, build_region_pdf
from app.report import build_district_report
from schemas import DistrictReport, IncidentExample, SeverityStat, ThematicGroupStat


def test_district_pdf_many_topics():
    themes = [
        ThematicGroupStat(group_name=f"Тема {i}", count=10 + i, percentage=3.0)
        for i in range(32)
    ]
    report = DistrictReport(
        district_id=1,
        district_name="Тестовый район",
        score=75,
        analytical_summary="Тестовая сводка.",
        total_incidents=500,
        top_category=themes[0].group_name,
        categories_count=32,
        resolved_pct=62.5,
        resolved_count=125,
        problem_count=200,
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 3, 31),
        themes_stat=themes,
        severity_stat=[
            SeverityStat(severity=i, label=f"L{i}", count=i * 5, percentage=float(i * 5))
            for i in range(5)
        ],
        incident_examples=[
            IncidentExample(text=f"Пример {i}", severity=2, label="Средняя") for i in range(3)
        ],
    )
    pdf = build_district_pdf(report)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 5_000


SAMPLE_REGION_REPORT = {
    "summary_text": "За период зафиксирован рост обращений по ЖКХ в трёх муниципалитетах.",
    "stats": {
        "start_date": "2025-01-01",
        "end_date": "2025-03-31",
        "rows_processed": 1200,
        "problem_count": 890,
    },
    "top3": [
        {
            "rank": 1,
            "district_id": 1,
            "муниципалитет": "г. Омск",
            "score": 82,
            "total_incidents": 500,
            "problem_count": 420,
            "critical_count": 12,
            "топ_тема": "ЖКХ",
            "summary_text": "Преобладают жалобы на отопление.",
        },
    ],
    "top10": [
        {
            "rank": i + 1,
            "district_id": i + 1,
            "муниципалитет": name,
            "score": 90 - i * 5,
            "total_incidents": 300 - i * 20,
            "problem_count": 250 - i * 15,
            "critical_count": max(0, 10 - i),
            "топ_тема": "ЖКХ" if i % 2 == 0 else "Дороги",
        }
        for i, name in enumerate(
            ["г. Омск", "Омский район", "Исilkul", "Калачинский", "Тарский"]
        )
    ],
    "all": [
        {
            "district_id": i + 1,
            "rank": i + 1,
            "муниципалитет": name,
            "score": 90 - i * 5,
            "total_incidents": 300 - i * 20,
            "problem_count": 250 - i * 15,
        }
        for i, name in enumerate(
            ["г. Омск", "Омский район", "Исilkul", "Калачинский", "Тарский"]
        )
    ],
    "topics": [
        {"муниципалитет": "г. Омск", "тема": "Отопление", "count": 120},
        {"муниципалитет": "г. Омск", "тема": "Мусор", "count": 80},
        {"муниципалитет": "Омский район", "тема": "Дороги", "count": 45},
    ],
    "reasons": [
        {
            "муниципалитет": "г. Омск",
            "топ_тема": "Отопление",
            "ключевые_темы": "Отопление(120); Мусор(80)",
            "summary_text": "Жалобы на низкую температуру в домах.",
        },
    ],
    "severity_breakdown": [
        {"муниципалитет": "г. Омск", "severity": 3, "label": "Высокая", "count": 100},
        {"муниципалитет": "г. Омск", "severity": 4, "label": "Критическая", "count": 12},
        {"муниципалитет": "г. Омск", "severity": 2, "label": "Средняя", "count": 200},
    ],
    "resolved_stats": [
        {"муниципалитет": "г. Омск", "problem_count": 420, "resolved_count": 210, "resolved_pct": 50.0},
        {"муниципалитет": "Омский район", "problem_count": 180, "resolved_count": 90, "resolved_pct": 50.0},
        {"муниципалитет": "Исilkul", "problem_count": 120, "resolved_count": 48, "resolved_pct": 40.0},
        {"муниципалитет": "Калачинский", "problem_count": 95, "resolved_count": 30, "resolved_pct": 31.6},
        {"муниципалитет": "Тарский", "problem_count": 80, "resolved_count": 20, "resolved_pct": 25.0},
    ],
}


def test_region_pdf_with_report_json():
    districts = []
    for row in SAMPLE_REGION_REPORT["all"]:
        result = build_district_report(
            SAMPLE_REGION_REPORT,
            int(row["district_id"]),
        )
        assert result is not None
        districts.append(result.data)

    pdf = build_region_pdf(
        districts,
        executive_summary=SAMPLE_REGION_REPORT["summary_text"],
        report=SAMPLE_REGION_REPORT,
    )
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 15_000
