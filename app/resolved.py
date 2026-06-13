"""Критерий решённости обращения по колонке «Итог» (AD)."""

from __future__ import annotations

import pandas as pd

RESOLVED_OUTCOMES = frozenset({"решено", "разъяснено", "перенаправлено"})
OUTCOME_COLUMNS = ("outcome", "итог")
_EMPTY = frozenset({"", "nan", "none", "<na>"})


def normalize_outcome(value) -> str:
    return str(value or "").strip().lower()


def is_resolved_outcome(value) -> bool:
    """Решено, если итог — «решено», «разъяснено» или «перенаправлено» (без учёта регистра)."""
    text = normalize_outcome(value)
    if not text or text in _EMPTY:
        return False
    if text in RESOLVED_OUTCOMES:
        return True
    return any(text.startswith(kw) for kw in RESOLVED_OUTCOMES)


def outcome_from_row(row: pd.Series) -> str | None:
    for col in OUTCOME_COLUMNS:
        if col in row.index:
            raw = str(row.get(col, "")).strip()
            if raw and raw.lower() not in _EMPTY:
                return raw
    return None


def is_resolved_row(row: pd.Series) -> bool:
    """Строка parquet/БД: итог из AD или ручная отметка (live / реестр)."""
    if is_resolved_outcome(outcome_from_row(row)):
        return True
    if "manually_resolved" in row.index and bool(row.get("manually_resolved")):
        return True
    return False


def filter_unresolved(df: pd.DataFrame) -> pd.DataFrame:
    """Строки без решённого итога (для скоринга)."""
    if df.empty:
        return df
    mask = ~df.apply(is_resolved_row, axis=1)
    return df.loc[mask].copy()


def outcome_column(df: pd.DataFrame) -> str | None:
    for col in OUTCOME_COLUMNS:
        if col in df.columns:
            return col
    return None
