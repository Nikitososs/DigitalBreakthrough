"""Статистика решённых проблем по МО."""

import pandas as pd

from app.report import build_district_report, build_resolved_stats


def test_build_resolved_stats_by_municipality():
    df = pd.DataFrame(
        {
            "муниципалитет": ["А", "А", "А", "Б", "Б"],
            "severity": [3, 2, 0, 4, 1],
            "итог": ["Решено", None, None, "Перенаправлено", "Отклонено"],
        }
    )
    stats = build_resolved_stats(df)
    by_muni = {row["муниципалитет"]: row for row in stats}
    assert by_muni["А"]["problem_count"] == 2
    assert by_muni["А"]["resolved_count"] == 1
    assert by_muni["А"]["resolved_pct"] == 50.0
    assert by_muni["Б"]["problem_count"] == 2
    assert by_muni["Б"]["resolved_count"] == 1
    assert by_muni["Б"]["resolved_pct"] == 50.0


def test_build_district_report_includes_resolved_pct():
    report = {
        "all": [
            {
                "district_id": 1,
                "муниципалитет": "А",
                "score": 80,
                "total_incidents": 10,
                "problem_count": 4,
            }
        ],
        "reasons": [{"муниципалитет": "А", "топ_тема": "ЖКХ"}],
        "topics": [],
        "severity_breakdown": [],
        "resolved_stats": [
            {
                "муниципалитет": "А",
                "problem_count": 4,
                "resolved_count": 3,
                "resolved_pct": 75.0,
            }
        ],
        "stats": {},
    }
    result = build_district_report(report, 1)
    assert result is not None
    assert result.data.resolved_pct == 75.0
    assert result.data.resolved_count == 3
    assert result.data.problem_count == 4
