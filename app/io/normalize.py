"""Нормализация колонок official_export и parquet-safe экспорт."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.io.identity import assign_stable_row_ids, dedupe_incidents
from app.text_clean import clean_appeal_text

RENAME_MAP = {
    "external_id": "id_обращения",
    "incident_number": "номер_инцидента",
    "workflow_step": "шаг_инцидента",
    "outcome": "итог",
    "created_at": "дата_создания",
    "closed_at": "дата_закрытия",
    "group": "группа",
    "topic": "тема",
    "region": "регион",
    "municipality": "муниципалитет",
    "settlement": "населенный_пункт",
    "street": "улица",
    "house": "дом",
    "incident_type": "тип_инцидента",
    "tags": "теги",
    "text": "текст",
}

INCIDENT_COLUMNS = tuple(RENAME_MAP.values()) + ("row_id",)
LABEL_COLUMNS = ("Метка_Класса", "Уровень_тяжести", "Уверенность", "severity", "is_problem", "manually_resolved")
LABELED_COLUMNS = INCIDENT_COLUMNS + LABEL_COLUMNS

INFERENCE_COLUMNS = {
    "группа": "Группа тем",
    "тема": "Тема",
    "текст": "Текст инцидента",
    "дата_создания": "Дата создания",
}


def _clean_str_series(series: pd.Series) -> pd.Series:
    return series.astype(str).replace({"nan": "", "None": "", "<NA>": ""}).str.strip()


def _clean_html_series(series: pd.Series) -> pd.Series:
    return _clean_str_series(series).map(clean_appeal_text)


def normalize_loaded(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in (
        "external_id",
        "incident_number",
        "workflow_step",
        "outcome",
        "group",
        "topic",
        "region",
        "settlement",
        "street",
        "house",
        "incident_type",
        "tags",
    ):
        if col not in out.columns:
            out[col] = ""

    missing = [c for c in ("municipality", "text") if c not in out.columns]
    if missing:
        raise ValueError(f"Не найдены обязательные поля: {missing}")

    for col in RENAME_MAP:
        if col in out.columns:
            out[col] = _clean_str_series(out[col])

    out = out.rename(columns=RENAME_MAP)
    for col in ("текст", "тема", "группа"):
        if col in out.columns:
            out[col] = _clean_html_series(out[col])
    keep = [c for c in LABELED_COLUMNS if c in out.columns and c != "row_id"]
    extra = [c for c in INCIDENT_COLUMNS if c in out.columns and c not in keep]
    out = out[keep + extra]
    out = assign_stable_row_ids(out)
    out, dedup_stats = dedupe_incidents(out)
    out.attrs["dedup"] = dedup_stats
    return out


def select_labeled_columns(df: pd.DataFrame) -> pd.DataFrame:
    keep = [c for c in LABELED_COLUMNS if c in df.columns]
    return df[keep].copy() if keep else df.copy()


def parquet_safe(df: pd.DataFrame) -> pd.DataFrame:
    out = select_labeled_columns(df)
    for col in out.columns:
        if col in ("row_id", "severity", "Метка_Класса") or col == "is_problem":
            continue
        if pd.api.types.is_bool_dtype(out[col]):
            continue
        if pd.api.types.is_numeric_dtype(out[col]):
            continue
        out[col] = out[col].map(lambda x: "" if pd.isna(x) else str(x))
    return out


def read_labeled_parquet(path: Path | str) -> pd.DataFrame:
    import pyarrow.parquet as pq

    path = Path(path)
    pf = pq.ParquetFile(path)
    names = [name for name in pf.schema_arrow.names if name in LABELED_COLUMNS]
    if not names:
        raise ValueError(f"В {path} нет известных колонок разметки")
    return pf.read(columns=names).to_pandas()


def to_inference_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for src, dst in INFERENCE_COLUMNS.items():
        if src in out.columns:
            out[dst] = out[src]
        elif dst not in out.columns:
            out[dst] = ""
    if "дата_создания" in out.columns:
        out["Дата создания"] = out["дата_создания"]
    elif "Дата создания" not in out.columns:
        out["Дата создания"] = ""
    return out
