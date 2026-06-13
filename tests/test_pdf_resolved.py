"""PDF: блок решённости проблем."""

from datetime import datetime

from app.pdf_report import (
    _aggregate_region_resolved,
    _district_resolved_metrics,
    build_district_pdf,
)
from schemas import DistrictReport, SeverityStat, ThematicGroupStat


def test_district_resolved_metrics():
    report = DistrictReport(
        district_id=1,
        district_name="г. Омск",
        score=70,
        analytical_summary="",
        total_incidents=100,
        top_category="ЖКХ",
        categories_count=2,
        resolved_pct=40.0,
        resolved_count=40,
        problem_count=100,
        themes_stat=[ThematicGroupStat(group_name="ЖКХ", count=60, percentage=60.0)],
        severity_stat=[SeverityStat(severity=2, label="Средняя", count=100, percentage=100.0)],
    )
    metrics = _district_resolved_metrics(report)
    assert metrics["resolved_count"] == 40
    assert metrics["open_count"] == 60
    assert metrics["resolved_pct"] == 40.0


def test_aggregate_region_resolved():
    report = {
        "resolved_stats": [
            {"муниципалитет": "A", "problem_count": 100, "resolved_count": 50, "resolved_pct": 50.0},
            {"муниципалитет": "B", "problem_count": 50, "resolved_count": 25, "resolved_pct": 50.0},
        ]
    }
    metrics = _aggregate_region_resolved(report, [])
    assert metrics["problem_count"] == 150
    assert metrics["resolved_count"] == 75
    assert metrics["open_count"] == 75
    assert metrics["resolved_pct"] == 50.0


def test_district_pdf_with_resolved_block():
    report = DistrictReport(
        district_id=2,
        district_name="Омский район",
        score=55,
        analytical_summary="Сводка.",
        total_incidents=300,
        top_category="Дороги",
        categories_count=3,
        resolved_pct=33.3,
        resolved_count=30,
        problem_count=90,
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 3, 31),
        themes_stat=[ThematicGroupStat(group_name="Дороги", count=50, percentage=55.0)],
        severity_stat=[SeverityStat(severity=2, label="Средняя", count=90, percentage=100.0)],
    )
    pdf = build_district_pdf(report)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 4_000
