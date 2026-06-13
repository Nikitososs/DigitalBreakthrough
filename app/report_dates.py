"""Парсинг дат обращений и вычисление периода отчёта.

Вынесено из app/report.py — листовой модуль (stdlib + pandas + app.io),
ни от чего в report.py не зависит. report.py реэкспортирует публичные имена.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.io import load_incidents, read_labeled_parquet

DATE_COLUMN = "дата_создания"
_ISO_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _prefer_dayfirst(values: pd.Series) -> bool:
    """False для ISO (YYYY-MM-DD), True для европейского DD.MM.YYYY."""
    for value in values.dropna().head(40):
        if isinstance(value, (datetime, pd.Timestamp)):
            continue
        text = str(value).strip()
        if _ISO_DATE_PREFIX.match(text):
            return False
        if re.match(r"^\d{1,2}\.", text) or re.match(r"^\d{1,2}/\d{1,2}/", text):
            return True
    return False


def _parse_date_column(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")
    dayfirst = _prefer_dayfirst(series)
    parsed = pd.to_datetime(series, errors="coerce", dayfirst=dayfirst)
    if int(parsed.notna().sum()) == 0:
        parsed = pd.to_datetime(series, errors="coerce", dayfirst=not dayfirst)
    return parsed


def compute_incident_date_range(df: pd.DataFrame) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Мин/макс даты создания обращений, если колонка распознана и парсится."""
    if df is None or df.empty:
        return None, None

    if DATE_COLUMN not in df.columns:
        return None, None
    min_rows = max(3, int(len(df) * 0.1))
    parsed = _parse_date_column(df[DATE_COLUMN])
    valid = parsed.notna()
    if int(valid.sum()) < min_rows:
        return None, None
    dates = parsed.loc[valid]
    return dates.min(), dates.max()


def _parse_report_date(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    text = str(value).strip()
    dayfirst = not bool(_ISO_DATE_PREFIX.match(text))
    ts = pd.to_datetime(text, errors="coerce", dayfirst=dayfirst)
    if pd.isna(ts):
        return None
    return ts.to_pydatetime()


def enrich_report_period(report: dict, cache_dir: Path | None = None) -> dict:
    """Дополняет stats периодом из labeled.parquet или input.xlsx (для старых report.json)."""
    stats = report.setdefault("stats", {})
    if stats.get("start_date") and stats.get("end_date"):
        return report

    start, end = None, None
    labeled_path = cache_dir / "labeled.parquet" if cache_dir else None
    if labeled_path is not None and labeled_path.exists():
        start, end = compute_incident_date_range(read_labeled_parquet(labeled_path))

    if (start is None or end is None) and cache_dir is not None:
        job_dir = cache_dir.parent
        for name in ("input.xlsx", "input.xls"):
            input_path = job_dir / name
            if not input_path.exists():
                continue
            try:
                start, end = compute_incident_date_range(load_incidents(input_path))
                if start is not None:
                    break
            except Exception:
                continue
    if start is not None:
        stats["start_date"] = start.strftime("%Y-%m-%d")
    if end is not None:
        stats["end_date"] = end.strftime("%Y-%m-%d")
    return report
