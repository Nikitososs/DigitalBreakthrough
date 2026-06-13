"""Стабильный ключ обращения (ID кабинета) и дедупликация при загрузке Excel."""

from __future__ import annotations

import pandas as pd

_EMPTY = {"", "nan", "none", "<na>", "null"}


def _clean_key(value) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in _EMPTY else text


def stable_row_id(external_id, incident_number, fallback_index: int) -> str:
    """
    Уникальный ключ строки для row_id / API «отметить решённым».

    Приоритет: B (ID кабинета) → C (номер инцидента) → порядковый индекс.
    """
    ext = _clean_key(external_id)
    if ext:
        return ext
    num = _clean_key(incident_number)
    if num:
        return f"no:{num}"
    return str(fallback_index)


def assign_stable_row_ids(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    ext_col = "id_обращения" if "id_обращения" in out.columns else None
    num_col = "номер_инцидента" if "номер_инцидента" in out.columns else None
    if not ext_col and not num_col:
        if "row_id" not in out.columns:
            out["row_id"] = range(len(out))
        return out

    row_ids: list[str] = []
    for i, row in out.iterrows():
        row_ids.append(
            stable_row_id(
                row.get(ext_col) if ext_col else "",
                row.get(num_col) if num_col else "",
                int(i) if isinstance(i, int) else len(row_ids),
            )
        )
    out["row_id"] = row_ids
    return out


def dedupe_incidents(df: pd.DataFrame, *, key_col: str = "row_id") -> tuple[pd.DataFrame, dict]:
    """
    Удаляет дубликаты по ключу. Оставляет строку с более поздней датой закрытия
    или последнюю в файле (актуальное состояние при повторной выгрузке).
    """
    if df.empty or key_col not in df.columns:
        return df, {"before": len(df), "after": len(df), "removed": 0}

    before = len(df)
    work = df.copy()
    work["_src_order"] = range(len(work))

    closed_col = "дата_закрытия" if "дата_закрытия" in work.columns else None
    if closed_col:
        work["_closed_sort"] = pd.to_datetime(work[closed_col], errors="coerce")
    else:
        work["_closed_sort"] = pd.NaT

    work = work.sort_values(
        by=["_closed_sort", "_src_order"],
        ascending=[False, False],
        na_position="last",
    )
    work = work.drop_duplicates(subset=[key_col], keep="first")
    work = work.sort_values("_src_order").drop(columns=["_src_order", "_closed_sort"])

    after = len(work)
    stats = {"before": before, "after": after, "removed": before - after}
    return work.reset_index(drop=True), stats
