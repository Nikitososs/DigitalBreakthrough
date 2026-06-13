"""PDF: категории по нерешённым и таблица долей с resolved_pct."""

import pandas as pd

from app.pdf_report import _categories_chart, _shares_table, _styles
from app.report import _build_severity_stat, _build_themes_stat, build_district_report
from schemas import ThematicGroupStat


def test_build_themes_stat_unresolved_counts():
    df = pd.DataFrame(
        {
            "муниципалитет": ["А", "А", "А", "А"],
            "тема": ["ЖКХ", "ЖКХ", "Дороги", "Дороги"],
            "severity": [2, 3, 2, 1],
            "итог": ["Решено", None, "Перенаправлено", "Отклонено"],
        }
    )
    stats = _build_themes_stat("А", [], 10, df)
    by_name = {s.group_name: s for s in stats}
    assert by_name["ЖКХ"].count == 1
    assert by_name["ЖКХ"].total_count == 2
    assert by_name["ЖКХ"].resolved_pct == 50.0
    assert by_name["Дороги"].count == 1
    assert by_name["Дороги"].resolved_pct == 50.0


def test_shares_table_excludes_fully_resolved():
    themes = [
        ThematicGroupStat(group_name="ЖКХ", count=0, percentage=40.0, total_count=10, resolved_pct=100.0),
        ThematicGroupStat(group_name="Дороги", count=5, percentage=60.0, total_count=8, resolved_pct=37.5),
    ]
    styles = _styles()
    table = _shares_table(themes, problem_total=18, styles=styles)
    assert table is not None
    rows = table._cellvalues
    assert len(rows) == 2  # header + one theme
    assert rows[1][0].text == "Дороги"
    assert "37.5%" in rows[1][3].text


def test_categories_chart_skips_zero_unresolved():
    themes = [
        ThematicGroupStat(group_name="ЖКХ", count=0, percentage=10.0, total_count=5, resolved_pct=100.0),
        ThematicGroupStat(group_name="Дороги", count=3, percentage=90.0, total_count=3, resolved_pct=0.0),
    ]
    chart = _categories_chart(themes, 170.0)
    assert chart is not None


def test_build_severity_stat_unresolved_only():
    df = pd.DataFrame(
        {
            "муниципалитет": ["А", "А", "А", "А"],
            "severity": [2, 3, 4, 2],
            "итог": ["Решено", None, "Перенаправлено", "Отклонено"],
        }
    )
    stats = _build_severity_stat("А", [], 10, df)
    by_sev = {s.severity: s for s in stats}
    assert by_sev[2].count == 1
    assert by_sev[3].count == 1
    assert 4 not in by_sev
    assert sum(s.count for s in stats) == 2


def test_district_report_themes_from_labeled():
    labeled = pd.DataFrame(
        {
            "муниципалитет": ["А", "А", "А"],
            "тема": ["ЖКХ", "ЖКХ", "Дороги"],
            "severity": [2, 2, 3],
            "итог": ["Решено", "Отклонено", "Отклонено"],
            "текст": ["a" * 50, "b" * 50, "c" * 50],
        }
    )
    report = {
        "all": [
            {
                "district_id": 1,
                "муниципалитет": "А",
                "score": 70,
                "total_incidents": 10,
                "problem_count": 3,
            }
        ],
        "reasons": [{"муниципалитет": "А", "топ_тема": "ЖКХ"}],
        "topics": [],
        "severity_breakdown": [],
        "stats": {},
    }
    result = build_district_report(report, 1, labeled_df=labeled)
    assert result is not None
    jkh = next(t for t in result.data.themes_stat if t.group_name == "ЖКХ")
    assert jkh.count == 1
    assert jkh.resolved_pct == 50.0
