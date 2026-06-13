"""Сводка по МО — только нерешённые проблемные обращения."""

import pandas as pd

from app.report import build_district_report, _unresolved_problems_for_muni


def test_unresolved_problems_for_muni_excludes_resolved():
    df = pd.DataFrame(
        {
            "муниципалитет": ["А", "А", "А", "А"],
            "severity": [3, 2, 4, 1],
            "итог": ["Решено", None, "Перенаправлено", "Отклонено"],
            "текст": ["a", "b", "c", "d"],
        }
    )
    problems = _unresolved_problems_for_muni(df, "А")
    assert len(problems) == 2
    assert set(problems["severity"].tolist()) == {2, 1}


def test_build_district_report_summary_fallback_unresolved_only():
    labeled = pd.DataFrame(
        {
            "муниципалитет": ["А"] * 4,
            "severity": [3, 2, 4, 1],
            "итог": ["Решено", None, "Перенаправлено", "Отклонено"],
            "текст": ["t1", "t2", "t3", "t4"],
            "тема": ["ЖКХ"] * 4,
            "группа": ["Г"] * 4,
        }
    )
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
        "reasons": [
            {
                "муниципалитет": "А",
                "топ_тема": "ЖКХ",
                "summary_paragraph": "Старая сводка по всем проблемам.",
            }
        ],
        "topics": [],
        "severity_breakdown": [],
        "resolved_stats": [],
        "stats": {},
    }
    result = build_district_report(report, 1, labeled_df=labeled)
    assert result is not None
    summary = result.data.analytical_summary
    assert "Старая сводка" not in summary
    assert "2 нерешённых" in summary
