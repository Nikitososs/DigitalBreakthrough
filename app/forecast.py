"""Прогноз обращений: weekly агрегация и линейный тренд."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.report_dates import DATE_COLUMN, _parse_date_column

MIN_TREND_WEEKS = 4
DEFAULT_HISTORY_WEEKS = 12
DISPLAY_HISTORY_WEEKS = 26
DISPLAY_MONTHLY_MAX = 24
RISK_EVAL_LABEL_LIMIT = 60
SLOPE_THRESHOLD = 0.5
TREND_PCT_THRESHOLD = 8.0
ALLOWED_HORIZONS = (2, 4, 8)
TOP_VOLUME_N = 10
HEATMAP_MUNI_N = 8
HEATMAP_WEEKS = 8
FORECAST_MAP_MUNI_N = 40

MUNI_COLUMNS = ("муниципалитет", "municipality", "district_name")
TOPIC_COLUMNS = ("тема", "topic", "theme")
GROUP_COLUMNS = ("группа", "group", "group_name")
AGENCY_COLUMNS = ("ведомство", "agency", "agency_name")
SEVERITY_LABELS = {
    0: "Не инцидент",
    1: "Низкая",
    2: "Средняя",
    3: "Высокая",
    4: "Критическая",
}


def _pick_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _week_start(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    return parsed.dt.to_period("W-MON").dt.start_time


def _prepare_problem_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    if "is_problem" in work.columns:
        mask = work["is_problem"].fillna(False).astype(bool)
        work = work.loc[mask]
    if DATE_COLUMN not in work.columns:
        return pd.DataFrame()
    work["_date"] = _parse_date_column(work[DATE_COLUMN])
    work = work.loc[work["_date"].notna()]
    if work.empty:
        return pd.DataFrame()
    work["_week"] = _week_start(work["_date"])
    return work


def _weekly_counts(df: pd.DataFrame, group_col: str | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["week", "count", "label"])

    if group_col:
        grouped = (
            df.groupby(["_week", group_col], dropna=False)
            .size()
            .reset_index(name="count")
        )
        grouped = grouped.rename(columns={group_col: "label", "_week": "week"})
        grouped["label"] = grouped["label"].astype(str).str.strip()
        grouped = grouped.loc[grouped["label"].ne("") & grouped["label"].ne("nan")]
        return grouped

    total = df.groupby("_week").size().reset_index(name="count")
    total["label"] = "Регион"
    return total.rename(columns={"_week": "week"})


def _linear_forecast(
    counts: np.ndarray,
    horizon: int,
    history_n: int,
) -> tuple[np.ndarray, float, str, int]:
    """Линейный тренд на последних N недель; при <4 недель — среднее."""
    n = len(counts)
    if n == 0:
        return np.zeros(horizon, dtype=float), 0.0, "low", 0

    tail_n = min(history_n, n)
    tail = counts[-tail_n:]
    mean_val = float(np.mean(tail)) if tail_n else 0.0

    if tail_n < MIN_TREND_WEEKS:
        preds = np.full(horizon, max(0.0, mean_val))
        return preds, 0.0, "low", tail_n

    x = np.arange(tail_n, dtype=float)
    y = tail.astype(float)
    slope, intercept = np.polyfit(x, y, 1)
    future_x = np.arange(tail_n, tail_n + horizon, dtype=float)
    preds = intercept + slope * future_x
    preds = np.maximum(0.0, preds)

    if mean_val > 0:
        trend_pct = (slope / mean_val) * 100.0
    else:
        trend_pct = 100.0 if slope > 0 else 0.0

    return preds, float(trend_pct), "normal", tail_n


def _risk_level(trend_pct: float, slope: float, confidence: str) -> str:
    if confidence == "low":
        return "низкая уверенность"
    if slope > SLOPE_THRESHOLD and trend_pct >= TREND_PCT_THRESHOLD:
        return "высокий"
    if slope > 0 and trend_pct > 0:
        return "средний"
    if trend_pct <= -TREND_PCT_THRESHOLD:
        return "снижение"
    return "стабильный"


def _build_series(
    weekly: pd.DataFrame,
    label: str,
    horizon: int,
    history_n: int,
) -> dict:
    subset = weekly.loc[weekly["label"] == label].sort_values("week")
    weeks = subset["week"].tolist()
    counts = subset["count"].astype(int).tolist()

    tail_n = min(history_n, len(counts))
    tail_counts = np.array(counts[-tail_n:], dtype=float) if tail_n else np.array([], dtype=float)
    preds, trend_pct, confidence, used_n = _linear_forecast(tail_counts, horizon, history_n)

    std_dev = float(np.std(tail_counts)) if len(tail_counts) > 1 else float(np.mean(tail_counts) * 0.15) if len(tail_counts) else 0.0

    slope = 0.0
    if used_n >= MIN_TREND_WEEKS and len(tail_counts) >= MIN_TREND_WEEKS:
        x = np.arange(used_n, dtype=float)
        slope = float(np.polyfit(x, tail_counts[-used_n:], 1)[0])

    points: list[dict] = []
    for w, c in zip(weeks, counts):
        points.append(
            {
                "period": w.isoformat() if hasattr(w, "isoformat") else str(w),
                "actual": int(c),
                "predicted": None,
                "is_forecast": False,
            }
        )

    last_week = weeks[-1] if weeks else None
    for i, pred in enumerate(preds):
        if last_week is not None:
            future_week = last_week + pd.Timedelta(weeks=i + 1)
            period = future_week.isoformat()
        else:
            period = f"forecast+{i + 1}"
        points.append(
            {
                "period": period,
                "actual": None,
                "predicted": round(float(pred), 1),
                "predicted_low": round(max(0.0, float(pred) - std_dev), 1),
                "predicted_high": round(float(pred) + std_dev, 1),
                "is_forecast": True,
            }
        )

    history_total = int(sum(counts))
    forecast_total = round(float(sum(preds)), 1)
    last_actual = int(counts[-1]) if counts else 0
    forecast_next = round(float(preds[0]), 1) if len(preds) else None

    return {
        "label": label,
        "points": points,
        "trend_pct": round(trend_pct, 1),
        "risk_level": _risk_level(trend_pct, slope, confidence),
        "confidence": confidence,
        "history_total": history_total,
        "forecast_total": forecast_total,
        "last_week_actual": last_actual,
        "forecast_next_week": forecast_next,
    }


def _rising_items(
    weekly: pd.DataFrame,
    horizon: int,
    history_n: int,
    min_total: int = 3,
    top_n: int = 10,
) -> list[dict]:
    if weekly.empty or "label" not in weekly.columns:
        return []

    rising: list[dict] = []
    allowed = _top_labels(weekly, RISK_EVAL_LABEL_LIMIT)
    for label in weekly["label"].unique():
        if label == "Регион" or label not in allowed:
            continue
        series = _build_series(weekly, label, horizon, history_n)
        total = sum(
            p["actual"] for p in series["points"] if p["actual"] is not None
        )
        if total < min_total:
            continue
        if series["trend_pct"] < TREND_PCT_THRESHOLD:
            continue
        tail = [
            p["actual"]
            for p in series["points"]
            if p["actual"] is not None
        ]
        tail_n = min(history_n, len(tail))
        if tail_n < MIN_TREND_WEEKS:
            continue
        x = np.arange(tail_n, dtype=float)
        slope = float(np.polyfit(x, np.array(tail[-tail_n:], dtype=float), 1)[0])
        if slope <= SLOPE_THRESHOLD:
            continue
        rising.append(series)

    rising.sort(key=lambda s: s["trend_pct"], reverse=True)
    return rising[:top_n]


def _declining_items(
    weekly: pd.DataFrame,
    horizon: int,
    history_n: int,
    min_total: int = 3,
    top_n: int = 10,
) -> list[dict]:
    if weekly.empty or "label" not in weekly.columns:
        return []

    declining: list[dict] = []
    allowed = _top_labels(weekly, RISK_EVAL_LABEL_LIMIT)
    for label in weekly["label"].unique():
        if label == "Регион" or label not in allowed:
            continue
        series = _build_series(weekly, label, horizon, history_n)
        total = sum(p["actual"] for p in series["points"] if p["actual"] is not None)
        if total < min_total:
            continue
        if series["trend_pct"] > -TREND_PCT_THRESHOLD:
            continue
        tail = [p["actual"] for p in series["points"] if p["actual"] is not None]
        tail_n = min(history_n, len(tail))
        if tail_n < MIN_TREND_WEEKS:
            continue
        x = np.arange(tail_n, dtype=float)
        slope = float(np.polyfit(x, np.array(tail[-tail_n:], dtype=float), 1)[0])
        if slope >= -SLOPE_THRESHOLD:
            continue
        declining.append(series)

    declining.sort(key=lambda s: s["trend_pct"])
    return declining[:top_n]


def _top_labels(weekly: pd.DataFrame, limit: int = RISK_EVAL_LABEL_LIMIT) -> set[str]:
    if weekly.empty:
        return set()
    totals = weekly.groupby("label")["count"].sum().sort_values(ascending=False)
    return set(totals.head(limit).index.astype(str))


def _slim_series(series: dict) -> dict:
    """Убирает длинные временные ряды из ответа API."""
    out = {k: v for k, v in series.items() if k != "points"}
    out["points"] = []
    return out


def _slim_series_list(items: list[dict]) -> list[dict]:
    return [_slim_series(s) for s in items]


def _slice_series_for_display(series: dict, max_history: int = DISPLAY_HISTORY_WEEKS) -> dict:
    points = series.get("points") or []
    history = [p for p in points if not p.get("is_forecast")]
    forecast = [p for p in points if p.get("is_forecast")]
    return {**series, "points": history[-max_history:] + forecast}


def _top_volume(weekly: pd.DataFrame, top_n: int = TOP_VOLUME_N, recent_weeks: int = 12) -> list[dict]:
    if weekly.empty or "week" not in weekly.columns:
        return []
    max_week = weekly["week"].max()
    cutoff = max_week - pd.Timedelta(weeks=recent_weeks - 1)
    recent = weekly.loc[weekly["week"] >= cutoff]
    totals = recent.groupby("label")["count"].sum().sort_values(ascending=False)
    total_all = int(totals.sum()) or 1
    return [
        {
            "label": str(label),
            "value": int(value),
            "share_pct": round(100.0 * value / total_all, 1),
        }
        for label, value in totals.head(top_n).items()
    ]


def _monthly_counts(prepared: pd.DataFrame) -> list[dict]:
    if prepared.empty:
        return []
    work = prepared.copy()
    work["_month"] = work["_date"].dt.to_period("M").dt.start_time
    monthly = work.groupby("_month").size().reset_index(name="count").sort_values("_month")
    if len(monthly) > DISPLAY_MONTHLY_MAX:
        monthly = monthly.tail(DISPLAY_MONTHLY_MAX)
    return [
        {
            "period": row["_month"].isoformat() if hasattr(row["_month"], "isoformat") else str(row["_month"]),
            "count": int(row["count"]),
        }
        for _, row in monthly.iterrows()
    ]


def _severity_breakdown(prepared: pd.DataFrame) -> list[dict]:
    if prepared.empty or "severity" not in prepared.columns:
        return []
    counts = prepared["severity"].fillna(0).astype(int).value_counts().sort_index()
    total = int(counts.sum()) or 1
    return [
        {
            "label": SEVERITY_LABELS.get(int(sev), f"Класс {sev}"),
            "severity": int(sev),
            "count": int(cnt),
            "share_pct": round(100.0 * cnt / total, 1),
        }
        for sev, cnt in counts.items()
        if int(sev) >= 1
    ]


def _group_breakdown(prepared: pd.DataFrame, top_n: int = TOP_VOLUME_N) -> list[dict]:
    col = _pick_column(prepared, GROUP_COLUMNS)
    if not col or prepared.empty:
        return []
    counts = prepared[col].astype(str).str.strip()
    counts = counts.loc[counts.ne("") & counts.ne("nan")]
    totals = counts.value_counts().head(top_n)
    total_all = int(prepared.shape[0]) or 1
    return [
        {
            "label": str(label),
            "value": int(value),
            "share_pct": round(100.0 * value / total_all, 1),
        }
        for label, value in totals.items()
    ]


def _risk_distribution(muni_weekly: pd.DataFrame, topic_weekly: pd.DataFrame, horizon: int, history_n: int) -> list[dict]:
    buckets = {"высокий": 0, "средний": 0, "стабильный": 0, "снижение": 0, "низкая уверенность": 0}
    labels_seen: set[str] = set()
    muni_labels = _top_labels(muni_weekly, RISK_EVAL_LABEL_LIMIT)
    topic_labels = _top_labels(topic_weekly, RISK_EVAL_LABEL_LIMIT)
    for weekly, allowed in ((muni_weekly, muni_labels), (topic_weekly, topic_labels)):
        if weekly.empty:
            continue
        for label in allowed:
            if label in labels_seen or label == "Регион":
                continue
            labels_seen.add(label)
            series = _build_series(weekly, label, horizon, history_n)
            level = series.get("risk_level", "стабильный")
            buckets[level] = buckets.get(level, 0) + 1
    return [{"label": k, "count": v} for k, v in buckets.items() if v > 0]


def _municipality_heatmap(muni_weekly: pd.DataFrame, top_m: int = HEATMAP_MUNI_N, weeks_n: int = HEATMAP_WEEKS) -> dict:
    if muni_weekly.empty:
        return {"municipalities": [], "weeks": [], "values": []}

    max_week = muni_weekly["week"].max()
    week_starts = [max_week - pd.Timedelta(weeks=weeks_n - 1 - i) for i in range(weeks_n)]
    week_labels = [w.strftime("%d.%m") if hasattr(w, "strftime") else str(w)[:10] for w in week_starts]

    recent = muni_weekly.loc[muni_weekly["week"].isin(week_starts)]
    top_muni = (
        recent.groupby("label")["count"]
        .sum()
        .sort_values(ascending=False)
        .head(top_m)
        .index.tolist()
    )

    values: list[list[int]] = []
    for muni in top_muni:
        row_vals: list[int] = []
        muni_data = recent.loc[recent["label"] == muni]
        for w in week_starts:
            val = muni_data.loc[muni_data["week"] == w, "count"].sum()
            row_vals.append(int(val))
        values.append(row_vals)

    return {
        "municipalities": [str(m) for m in top_muni],
        "weeks": week_labels,
        "values": values,
    }


def _trend_to_forecast_score(trend_pct: float) -> int:
    """Индекс «ожидаемой нагрузки» для раскраски карты (выше = хуже прогноз)."""
    if trend_pct >= 25:
        return int(min(98, 75 + trend_pct * 0.6))
    if trend_pct >= 8:
        return int(min(74, 52 + trend_pct))
    if trend_pct <= -8:
        return int(max(8, 35 + trend_pct * 0.8))
    return 40


def _forecast_map_districts(
    muni_weekly: pd.DataFrame,
    horizon: int,
    history_n: int,
    top_n: int = FORECAST_MAP_MUNI_N,
) -> list[dict]:
    if muni_weekly.empty or "label" not in muni_weekly.columns:
        return []

    totals = muni_weekly.groupby("label")["count"].sum().sort_values(ascending=False)
    labels = [str(lb) for lb in totals.head(top_n).index if str(lb) != "Регион"]

    districts: list[dict] = []
    for label in labels:
        series = _build_series(muni_weekly, label, horizon, history_n)
        trend = float(series.get("trend_pct") or 0)
        districts.append(
            {
                "id": label,
                "name": label,
                "score": _trend_to_forecast_score(trend),
                "trend_pct": round(trend, 1),
                "risk_level": series.get("risk_level", "стабильный"),
                "forecast_next_week": series.get("forecast_next_week"),
            }
        )
    districts.sort(key=lambda d: d["score"], reverse=True)
    return districts


def _prepare_critical_df(df: pd.DataFrame) -> pd.DataFrame:
    prepared = _prepare_problem_df(df)
    if prepared.empty or "severity" not in prepared.columns:
        return pd.DataFrame()
    return prepared.loc[prepared["severity"].fillna(0).astype(int) >= 3]


def _data_quality_metrics(df: pd.DataFrame, jobs_count: int, last_upload: str | None) -> dict:
    n = len(df)
    if n == 0:
        return {
            "address_pct": 0.0,
            "geocode_pct": 0.0,
            "agencies": 0,
            "closed_at_pct": 0.0,
            "jobs_count": jobs_count,
            "last_upload": last_upload or None,
        }
    addr = int(df["has_address"].fillna(False).astype(bool).sum()) if "has_address" in df.columns else 0
    geo = int(df["is_geocoded"].fillna(False).astype(bool).sum()) if "is_geocoded" in df.columns else 0
    closed = 0
    if "closed_at" in df.columns:
        closed = int(pd.to_datetime(df["closed_at"], errors="coerce").notna().sum())
    agencies = 0
    agency_col = _pick_column(df, AGENCY_COLUMNS)
    if agency_col:
        agencies = int(
            df[agency_col].astype(str).str.strip().replace({"": None, "nan": None}).dropna().nunique()
        )
    return {
        "address_pct": round(100.0 * addr / n, 1),
        "geocode_pct": round(100.0 * geo / n, 1),
        "agencies": agencies,
        "closed_at_pct": round(100.0 * closed / n, 1),
        "jobs_count": jobs_count,
        "last_upload": last_upload or None,
    }


def _processing_stats(df: pd.DataFrame, max_weeks: int = DISPLAY_HISTORY_WEEKS) -> dict:
    empty = {
        "available": False,
        "median_days": None,
        "p90_days": None,
        "closed_count": 0,
        "open_count": 0,
        "closed_share_pct": 0.0,
        "weekly_flow": [],
        "slowest_agencies": [],
    }
    if df.empty or "closed_at" not in df.columns or DATE_COLUMN not in df.columns:
        return empty

    work = df.copy()
    work["_created"] = _parse_date_column(work[DATE_COLUMN])
    work["_closed"] = pd.to_datetime(work["closed_at"], errors="coerce")
    closed_mask = work["_closed"].notna() & work["_created"].notna()
    closed_n = int(closed_mask.sum())
    total_n = len(work)
    closed_share = round(100.0 * closed_n / total_n, 1) if total_n else 0.0

    if closed_n < 5:
        return {
            **empty,
            "closed_count": closed_n,
            "open_count": total_n - closed_n,
            "closed_share_pct": closed_share,
        }

    days = (work.loc[closed_mask, "_closed"] - work.loc[closed_mask, "_created"]).dt.total_seconds() / 86400.0
    days = days.loc[(days >= 0) & (days <= 730)]
    if days.empty:
        return {
            **empty,
            "closed_count": closed_n,
            "open_count": total_n - closed_n,
            "closed_share_pct": closed_share,
        }

    median_days = round(float(days.median()), 1)
    p90_days = round(float(days.quantile(0.9)), 1)

    work["_week_created"] = _week_start(work["_created"])
    work["_week_closed"] = _week_start(work["_closed"])
    created_w = work.groupby("_week_created").size().reset_index(name="created")
    closed_w = work.loc[closed_mask].groupby("_week_closed").size().reset_index(name="closed")
    if not created_w.empty:
        max_week = created_w["_week_created"].max()
        cutoff = max_week - pd.Timedelta(weeks=max_weeks - 1)
        created_w = created_w.loc[created_w["_week_created"] >= cutoff]
        closed_w = closed_w.loc[closed_w["_week_closed"] >= cutoff]
    weeks = sorted(set(created_w["_week_created"].tolist()) | set(closed_w["_week_closed"].tolist()))
    created_map = dict(zip(created_w["_week_created"], created_w["created"]))
    closed_map = dict(zip(closed_w["_week_closed"], closed_w["closed"]))
    weekly_flow = [
        {
            "period": w.isoformat() if hasattr(w, "isoformat") else str(w),
            "created": int(created_map.get(w, 0)),
            "closed": int(closed_map.get(w, 0)),
        }
        for w in weeks
    ]

    slowest: list[dict] = []
    agency_col = _pick_column(work, AGENCY_COLUMNS)
    if agency_col:
        subset = work.loc[closed_mask].copy()
        subset["_days"] = (subset["_closed"] - subset["_created"]).dt.total_seconds() / 86400.0
        subset = subset.loc[(subset["_days"] >= 0) & (subset["_days"] <= 730)]
        subset[agency_col] = subset[agency_col].astype(str).str.strip()
        subset = subset.loc[subset[agency_col].ne("") & subset[agency_col].ne("nan")]
        if not subset.empty:
            grouped = subset.groupby(agency_col)["_days"].agg(["median", "count"]).reset_index()
            grouped = grouped.loc[grouped["count"] >= 3].sort_values("median", ascending=False).head(10)
            slowest = [
                {
                    "label": str(row[agency_col]),
                    "median_days": round(float(row["median"]), 1),
                    "count": int(row["count"]),
                }
                for _, row in grouped.iterrows()
            ]

    return {
        "available": True,
        "median_days": median_days,
        "p90_days": p90_days,
        "closed_count": closed_n,
        "open_count": total_n - closed_n,
        "closed_share_pct": closed_share,
        "weekly_flow": weekly_flow,
        "slowest_agencies": slowest,
    }


def _compute_kpis(
    prepared: pd.DataFrame,
    region_series: dict,
    *,
    rising_muni: list[dict],
    rising_topics: list[dict],
    declining_muni: list[dict],
    declining_topics: list[dict],
    muni_col: str | None,
    topic_col: str | None,
) -> dict:
    history = [p for p in region_series.get("points", []) if not p.get("is_forecast") and p.get("actual") is not None]
    forecast = [p for p in region_series.get("points", []) if p.get("is_forecast") and p.get("predicted") is not None]
    counts = [p["actual"] for p in history]
    preds = [p["predicted"] for p in forecast]
    tail_12 = counts[-12:] if len(counts) >= 12 else counts

    peak_count = max(counts) if counts else 0
    peak_date = None
    if counts:
        peak_idx = counts.index(peak_count)
        peak_date = history[peak_idx].get("period")

    date_from = prepared["_date"].min() if not prepared.empty else None
    date_to = prepared["_date"].max() if not prepared.empty else None

    return {
        "avg_weekly_12w": round(float(np.mean(tail_12)), 1) if tail_12 else 0.0,
        "forecast_total": round(float(sum(preds)), 0) if preds else 0.0,
        "forecast_avg_weekly": round(float(np.mean(preds)), 1) if preds else 0.0,
        "peak_week_count": int(peak_count),
        "peak_week_date": peak_date,
        "date_from": date_from.strftime("%Y-%m-%d") if date_from is not None and pd.notna(date_from) else None,
        "date_to": date_to.strftime("%Y-%m-%d") if date_to is not None and pd.notna(date_to) else None,
        "municipalities": int(prepared[muni_col].nunique()) if muni_col else 0,
        "topics": int(prepared[topic_col].nunique()) if topic_col else 0,
        "rising_municipalities": len(rising_muni),
        "rising_topics": len(rising_topics),
        "declining_municipalities": len(declining_muni),
        "declining_topics": len(declining_topics),
        "history_weeks": len(counts),
    }


def _summary_text(
    region_series: dict,
    rising_muni: list[dict],
    rising_topics: list[dict],
    horizon: int,
) -> str:
    parts: list[str] = []
    trend = region_series.get("trend_pct", 0)
    risk = region_series.get("risk_level", "стабильный")

    if trend > TREND_PCT_THRESHOLD:
        parts.append(
            f"По региону ожидается рост проблемных обращений (~{trend:+.0f}% тренд на {horizon} нед.)."
        )
    elif trend < -TREND_PCT_THRESHOLD:
        parts.append(
            f"По региону прогнозируется снижение обращений (~{trend:+.0f}% тренд)."
        )
    else:
        parts.append("Динамика обращений в регионе остаётся стабильной.")

    parts.append(f"Уровень риска: {risk}.")

    if rising_muni:
        names = ", ".join(s["label"] for s in rising_muni[:3])
        parts.append(f"Растущие риски по МО: {names}.")
    if rising_topics:
        names = ", ".join(s["label"] for s in rising_topics[:3])
        parts.append(f"Растущие темы: {names}.")

    conf = region_series.get("confidence", "normal")
    if conf == "low":
        parts.append("Низкая уверенность прогноза: менее 4 недель истории.")

    return " ".join(parts)


def build_forecast(
    df: pd.DataFrame,
    horizon_weeks: int = 4,
    history_weeks: int = DEFAULT_HISTORY_WEEKS,
    *,
    incident_count: int | None = None,
    jobs_count: int | None = None,
    last_upload: str | None = None,
) -> dict:
    """Собирает прогноз из DataFrame обращений (обычно вся выборка из БД)."""
    if horizon_weeks not in ALLOWED_HORIZONS:
        horizon_weeks = 4

    prepared = _prepare_problem_df(df)
    generated_at = datetime.now(timezone.utc)

    if prepared.empty:
        empty_series = {
            "label": "Регион",
            "points": [],
            "trend_pct": 0.0,
            "risk_level": "низкая уверенность",
            "confidence": "low",
            "history_total": 0,
            "forecast_total": 0.0,
            "last_week_actual": 0,
            "forecast_next_week": None,
        }
        empty_kpis = _compute_kpis(
            prepared,
            empty_series,
            rising_muni=[],
            rising_topics=[],
            declining_muni=[],
            declining_topics=[],
            muni_col=None,
            topic_col=None,
        )
        empty_critical = {**empty_series, "label": "Критичные (3–4)"}
        return {
            "source": "database",
            "incident_count": incident_count or 0,
            "jobs_count": jobs_count or 0,
            "horizon_weeks": horizon_weeks,
            "history_weeks": history_weeks,
            "region_series": empty_series,
            "region_chart": empty_series,
            "critical_chart": empty_critical,
            "monthly_series": [],
            "kpis": empty_kpis,
            "data_quality": _data_quality_metrics(prepared, jobs_count or 0, last_upload),
            "processing": _processing_stats(prepared),
            "top_municipalities": [],
            "top_topics": [],
            "top_groups": [],
            "top_agencies": [],
            "severity_breakdown": [],
            "risk_distribution": [],
            "heatmap": {"municipalities": [], "weeks": [], "values": []},
            "map_districts": [],
            "rising_municipalities": [],
            "rising_topics": [],
            "declining_municipalities": [],
            "declining_topics": [],
            "summary_text": "Недостаточно данных для прогноза: в архиве нет проблемных обращений с датами.",
            "generated_at": generated_at,
        }

    region_weekly = _weekly_counts(prepared)

    muni_col = _pick_column(prepared, MUNI_COLUMNS)
    topic_col = _pick_column(prepared, TOPIC_COLUMNS)
    agency_col = _pick_column(prepared, AGENCY_COLUMNS)

    muni_weekly = _weekly_counts(prepared, muni_col) if muni_col else pd.DataFrame()
    topic_weekly = _weekly_counts(prepared, topic_col) if topic_col else pd.DataFrame()
    agency_weekly = _weekly_counts(prepared, agency_col) if agency_col else pd.DataFrame()

    critical_prepared = _prepare_critical_df(df)
    critical_weekly = _weekly_counts(critical_prepared)
    critical_series = _build_series(critical_weekly, "Регион", horizon_weeks, history_weeks)
    critical_series["label"] = "Критичные (3–4)"

    region_series = _build_series(region_weekly, "Регион", horizon_weeks, history_weeks)
    rising_muni = _rising_items(muni_weekly, horizon_weeks, history_weeks)
    rising_topics = _rising_items(topic_weekly, horizon_weeks, history_weeks)
    declining_muni = _declining_items(muni_weekly, horizon_weeks, history_weeks)
    declining_topics = _declining_items(topic_weekly, horizon_weeks, history_weeks)

    summary = _summary_text(region_series, rising_muni, rising_topics, horizon_weeks)

    count = incident_count if incident_count is not None else len(prepared)
    region_chart = _slice_series_for_display(region_series)
    critical_chart = _slice_series_for_display(critical_series)
    return {
        "source": "database",
        "incident_count": count,
        "jobs_count": jobs_count or 0,
        "horizon_weeks": horizon_weeks,
        "history_weeks": history_weeks,
        "region_series": region_chart,
        "region_chart": region_chart,
        "critical_chart": critical_chart,
        "monthly_series": _monthly_counts(prepared),
        "kpis": _compute_kpis(
            prepared,
            region_series,
            rising_muni=rising_muni,
            rising_topics=rising_topics,
            declining_muni=declining_muni,
            declining_topics=declining_topics,
            muni_col=muni_col,
            topic_col=topic_col,
        ),
        "data_quality": _data_quality_metrics(prepared, jobs_count or 0, last_upload),
        "processing": _processing_stats(prepared),
        "top_municipalities": _top_volume(muni_weekly),
        "top_topics": _top_volume(topic_weekly),
        "top_groups": _group_breakdown(prepared),
        "top_agencies": _top_volume(agency_weekly),
        "severity_breakdown": _severity_breakdown(prepared),
        "risk_distribution": _risk_distribution(muni_weekly, topic_weekly, horizon_weeks, history_weeks),
        "heatmap": _municipality_heatmap(muni_weekly),
        "map_districts": _forecast_map_districts(muni_weekly, horizon_weeks, history_weeks),
        "rising_municipalities": _slim_series_list(rising_muni),
        "rising_topics": _slim_series_list(rising_topics),
        "declining_municipalities": _slim_series_list(declining_muni),
        "declining_topics": _slim_series_list(declining_topics),
        "summary_text": summary,
        "generated_at": generated_at,
    }
