"""Parquet-safe экспорт labeled колонок."""

import pandas as pd

from app.io import parquet_safe, select_labeled_columns


def test_select_labeled_columns():
    df = pd.DataFrame(
        {
            "дата_создания": ["01.01.2024"],
            "муниципалитет": ["Омск г.о."],
            "текст": ["тест"],
            "severity": [2],
            "is_problem": [True],
            "extra_col": ["drop"],
        }
    )
    out = select_labeled_columns(df)
    assert "extra_col" not in out.columns
    assert "severity" in out.columns


def test_parquet_safe_roundtrip(tmp_path, test_xlsx_path):
    from app.io import load_incidents

    df = load_incidents(test_xlsx_path).head(100)
    df["severity"] = 1
    df["is_problem"] = True
    safe = parquet_safe(df)
    path = tmp_path / "labeled.parquet"
    safe.to_parquet(path, index=False)
    back = pd.read_parquet(path)
    assert len(back) == 100
    assert "текст" in back.columns
