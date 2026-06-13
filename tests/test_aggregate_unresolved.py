"""Скоринг только по нерешённым обращениям."""

import pandas as pd

from app.aggregate import build_municipality_rankings
from app.config.settings import PipelineSettings


def test_score_ignores_resolved_outcomes(tmp_path):
    df = pd.DataFrame(
        {
            "муниципалитет": ["А", "А", "Б", "Б", "В", "В"],
            "severity": [4, 4, 2, 2, 3, 4],
            "итог": ["Решено", "Отклонено", "Разъяснено", "Отклонено", "Решено", "Перенаправлено"],
        }
    )
    cfg = PipelineSettings(
        input_path=tmp_path / "in.xlsx",
        output_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
    )
    top_all, _, _ = build_municipality_rankings(df, cfg)
    by_muni = {row["муниципалитет"]: row for row in top_all.to_dict("records")}
    assert by_muni["А"]["score"] > by_muni["Б"]["score"]
    assert by_muni["В"]["score"] == 5
