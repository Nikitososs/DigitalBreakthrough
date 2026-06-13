"""Стабильный ключ и дедупликация обращений."""

import pandas as pd

from app.io.identity import assign_stable_row_ids, dedupe_incidents, stable_row_id


def test_stable_row_id_prefers_external_id():
    assert stable_row_id("39520480", "717475", 0) == "39520480"
    assert stable_row_id("", "717475", 3) == "no:717475"
    assert stable_row_id("", "", 7) == "7"


def test_assign_stable_row_ids_from_columns():
    df = pd.DataFrame(
        {
            "id_обращения": ["100", "200", ""],
            "номер_инцидента": ["1", "2", "99"],
            "текст": ["a", "b", "c"],
        }
    )
    out = assign_stable_row_ids(df)
    assert list(out["row_id"]) == ["100", "200", "no:99"]


def test_dedupe_keeps_latest_closed():
    df = pd.DataFrame(
        {
            "row_id": ["100", "100", "200"],
            "дата_закрытия": ["2025-01-01", "2025-06-01", "2025-03-01"],
            "текст": ["old", "new", "x"],
        }
    )
    out, stats = dedupe_incidents(df)
    assert stats["removed"] == 1
    assert len(out) == 2
    assert out.loc[out["row_id"] == "100", "текст"].iloc[0] == "new"
