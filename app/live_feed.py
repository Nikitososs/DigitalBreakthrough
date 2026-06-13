"""Загрузка пула размеченных обращений задачи из labeled.parquet."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.io import read_labeled_parquet


def _labeled_path(task_id: str, jobs_dir: Path) -> Path:
    return jobs_dir / task_id / "cache" / "labeled.parquet"


def load_labeled_pool(task_id: str, jobs_dir: Path) -> pd.DataFrame:
    path = _labeled_path(task_id, jobs_dir)
    if not path.is_file():
        raise FileNotFoundError("Размеченные данные не найдены (задача не завершена?)")
    df = read_labeled_parquet(path)
    if df.empty or "текст" not in df.columns:
        raise ValueError("В labeled.parquet нет обращений")
    work = df.copy()
    work["текст"] = work["текст"].astype(str).str.strip()
    work = work[work["текст"].str.len() >= 40]
    if work.empty:
        raise ValueError("Нет обращений с достаточной длиной текста")
    return work
