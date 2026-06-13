"""Раскладка официальной выгрузки: тестовый / основной файл.xlsx."""

from __future__ import annotations

import pandas as pd

# 47 колонок выгрузки кабинета: B/C — ключи, R…AR — аналитика, Q/AD — статус закрытия.
OFFICIAL_EXPORT_COLUMN_LETTERS = {
    "external_id": "B",
    "incident_number": "C",
    "workflow_step": "Q",
    "outcome": "AD",
    "created_at": "R",
    "closed_at": "S",
    "group": "T",
    "topic": "U",
    "region": "V",
    "municipality": "W",
    "settlement": "X",
    "street": "Y",
    "house": "Z",
    "incident_type": "AC",
    "text": "AI",
    "tags": "AR",
}

# Обратная совместимость с прежним именем в тестах.
CABINET_EXPORT_COLUMN_LETTERS = OFFICIAL_EXPORT_COLUMN_LETTERS


def excel_col_to_index(letters: str) -> int:
    n = 0
    for ch in letters.upper().strip():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def layout_usecols(layout: dict[str, str]) -> list[int]:
    return sorted(excel_col_to_index(letter) for letter in layout.values())


def dataframe_from_layout(raw: pd.DataFrame, layout: dict[str, str], usecols: list[int]) -> pd.DataFrame:
    pos = {idx: i for i, idx in enumerate(usecols)}
    data = {key: raw.iloc[:, pos[excel_col_to_index(letter)]] for key, letter in layout.items()}
    out = pd.DataFrame(data)
    out.attrs["column_layout"] = "official_export"
    return out
