"""Загрузка Excel: тестовый / основной файл (R…Z, AC, AI, AR)."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from app.io.layouts import (
    CABINET_EXPORT_COLUMN_LETTERS,
    dataframe_from_layout,
    layout_usecols,
)
from app.io.normalize import normalize_loaded

__all__ = ["load_incidents", "resolve_excel_engine"]


def resolve_excel_engine() -> str:
    pref = os.environ.get("EXCEL_ENGINE", "auto").strip().lower()
    if pref == "openpyxl":
        return "openpyxl"
    if pref == "calamine":
        return "calamine"
    try:
        import python_calamine  # noqa: F401

        return "calamine"
    except ImportError:
        return "openpyxl"


def load_incidents(path: Path | str) -> pd.DataFrame:
    """
    Загружает официальную выгрузку: R,S,T,U,V,W,X,Y,Z,AC,AI,AR (header=0).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    engine = resolve_excel_engine()
    layout = dict(CABINET_EXPORT_COLUMN_LETTERS)
    usecols = layout_usecols(layout)
    raw = pd.read_excel(path, header=0, engine=engine, usecols=usecols)
    return normalize_loaded(dataframe_from_layout(raw, layout, usecols))
