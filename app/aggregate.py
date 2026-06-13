"""Агрегация и ранжирование муниципалитетов по индексу проблемности."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.config.settings import PipelineSettings
from app.resolved import filter_unresolved

# Экспоненциальные веса тяжести классов 0–4
SEVERITY_WEIGHTS: dict[int, int] = {0: 0, 1: 1, 2: 5, 3: 20, 4: 100}

_INVALID_MUNI = {"", "nan", "none", "<na>"}


def _is_valid_municipality(name) -> bool:
    if name is None or (isinstance(name, float) and np.isnan(name)):
        return False
    return str(name).strip().lower() not in _INVALID_MUNI


def _filter_valid_municipalities(df: pd.DataFrame, district_col: str) -> pd.DataFrame:
    if district_col not in df.columns:
        return df
    mask = df[district_col].map(_is_valid_municipality)
    return df.loc[mask].copy()


def _rating_score(labels: list[int]) -> float:
    raw_score = sum(SEVERITY_WEIGHTS.get(int(label), 0) for label in labels)
    return raw_score / np.log1p(len(labels))


def _health_score(rating_score: float, max_rating: float) -> int:
    """Индекс проблемности: 5 — минимум проблем, 100 — максимум в срезе.

    Логарифмическая нормализация: один крупный центр (напр. Омск г.о.)
    не сжимает остальные муниципалитеты в узкий диапазон.
    """
    if max_rating <= 0 or rating_score <= 0:
        return 5
    ratio = min(1.0, np.log1p(rating_score) / np.log1p(max_rating))
    return min(100, max(5, int(5 + ratio * 95)))


def calculate_districts_health(
    df: pd.DataFrame,
    district_col: str = "муниципалитет",
    pred_col: str = "severity",
) -> pd.DataFrame:
    """
    Рассчитывает индекс проблемности для всех районов.
    5 — минимум проблем, 100 — худшая ситуация в срезе.
    Штраф нормируется на log(1 + N), чтобы крупные районы не доминировали только объёмом.
    """
    if district_col not in df.columns:
        raise ValueError(f"Колонка {district_col!r} не найдена")
    if pred_col not in df.columns:
        raise ValueError(f"Колонка {pred_col!r} не найдена")

    df = _filter_valid_municipalities(df, district_col)
    if df.empty:
        return pd.DataFrame()

    district_scores: dict[str, float] = {}
    for district, group in df.groupby(district_col, dropna=False):
        labels = group[pred_col].astype(int).tolist()
        if labels:
            district_scores[str(district)] = _rating_score(labels)

    max_rating = max(district_scores.values()) if district_scores else 0.0

    reports: list[dict] = []
    for district, rating in district_scores.items():
        district_data = df[df[district_col].astype(str) == district]
        labels = district_data[pred_col].astype(int)
        reports.append(
            {
                "муниципалитет": district,
                "total_incidents": len(district_data),
                "problem_count": int((labels > 0).sum()),
                "critical_count": int((labels == 4).sum()),
                "rating_score": round(rating, 4),
                "health_score": _health_score(rating, max_rating),
            }
        )

    if not reports:
        return pd.DataFrame()

    result = pd.DataFrame(reports)
    result = result.sort_values("health_score", ascending=False).reset_index(drop=True)
    result["rank"] = range(1, len(result) + 1)
    result["district_id"] = result["rank"]
    result["score"] = result["health_score"]
    return result


def build_municipality_rankings(
    df: pd.DataFrame,
    cfg: PipelineSettings,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if "severity" not in df.columns:
        raise ValueError("В размеченных данных нет колонки severity")
    pred_col = "severity"
    empty_cols = [
        "муниципалитет",
        "total_incidents",
        "problem_count",
        "critical_count",
        "rating_score",
        "health_score",
        "rank",
        "district_id",
        "score",
        "severity_mean",
        "severity_p90",
        "severity_sum",
        "high_count",
        "problem_share",
    ]

    full_df = _filter_valid_municipalities(df, "муниципалитет")
    if full_df.empty:
        empty = pd.DataFrame(columns=empty_cols)
        return empty, empty, empty

    scoring_df = filter_unresolved(full_df)
    health_df = calculate_districts_health(scoring_df, district_col="муниципалитет", pred_col=pred_col)

    sev = pd.to_numeric(full_df[pred_col], errors="coerce").fillna(0).astype(int)
    totals = (
        full_df.assign(_sev=sev)
        .groupby("муниципалитет", dropna=False)
        .agg(
            total_incidents=("_sev", "size"),
            problem_count=("_sev", lambda s: int((s > 0).sum())),
            critical_count=("_sev", lambda s: int((s == 4).sum())),
        )
        .reset_index()
    )

    if health_df.empty:
        agg = totals.copy()
        agg["rating_score"] = 0.0
        agg["health_score"] = 5
        agg["score"] = 5
    else:
        agg = totals.merge(
            health_df.drop(columns=["total_incidents", "problem_count", "critical_count"], errors="ignore"),
            on="муниципалитет",
            how="left",
        )
        agg["health_score"] = agg["health_score"].fillna(5).astype(int)
        agg["score"] = agg["health_score"]
        agg["rating_score"] = agg["rating_score"].fillna(0.0)

    score_source = scoring_df if not scoring_df.empty else full_df.iloc[0:0]
    if not score_source.empty:
        extra = (
            score_source.groupby("муниципалитет", dropna=False)
            .agg(
                severity_mean=(pred_col, "mean"),
                severity_p90=(pred_col, lambda s: s.quantile(0.9) if len(s) else 0),
                severity_sum=(pred_col, "sum"),
                high_count=(pred_col, lambda s: (s.astype(int) >= 3).sum()),
            )
            .reset_index()
        )
        agg = agg.merge(extra, on="муниципалитет", how="left")
    else:
        agg["severity_mean"] = 0.0
        agg["severity_p90"] = 0.0
        agg["severity_sum"] = 0
        agg["high_count"] = 0

    agg["problem_share"] = (agg["problem_count"] / agg["total_incidents"].clip(lower=1)).round(4)
    agg = agg.loc[agg["total_incidents"] > 0].reset_index(drop=True)
    agg = agg.sort_values("health_score", ascending=False).reset_index(drop=True)
    agg["rank"] = range(1, len(agg) + 1)
    agg["district_id"] = agg["rank"]
    agg["score"] = agg["health_score"]

    top_n = agg.head(cfg.top_municipalities).copy()
    top_hot = agg.head(cfg.top_hotspots).copy()
    return agg, top_n, top_hot
