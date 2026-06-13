"""Сборка report.json для live-потока (live0000) из Postgres."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import select

from app.aggregate import build_municipality_rankings
from app.breakdown import attach_reasons_to_rankings, build_topic_group_breakdown
from app.config.settings import PipelineSettings
from app.db.models import StoredIncident
from app.db.session import get_session
from app.report import _df_to_records, build_resolved_stats, build_severity_breakdown
from app.report_dates import compute_incident_date_range


def load_task_incidents_df(task_id: str) -> pd.DataFrame:
    with get_session() as session:
        rows = session.scalars(
            select(StoredIncident).where(StoredIncident.task_id == task_id)
        ).all()
        records = [
            {
                "row_id": r.row_id,
                "муниципалитет": r.municipality or "",
                "населенный_пункт": r.settlement or "",
                "улица": r.street or "",
                "дом": r.house or "",
                "текст": r.text or "",
                "группа": r.group_name or "",
                "тема": r.topic or "",
                "severity": int(r.severity),
                "is_problem": bool(r.is_problem),
                "дата_создания": r.created_at,
                "итог": r.outcome or "",
                "outcome": r.outcome or "",
                "manually_resolved": bool(r.manually_resolved),
            }
            for r in rows
        ]
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def build_live_report_from_db(task_id: str) -> dict:
    df = load_task_incidents_df(task_id)
    if df.empty:
        return {
            "summary_text": "Live-поток: пока нет обращений граждан",
            "top3": [],
            "top10": [],
            "all": [],
            "topics": [],
            "groups": [],
            "reasons": [],
            "severity_breakdown": [],
            "resolved_stats": [],
            "stats": {
                "rows_processed": 0,
                "problem_count": 0,
                "municipality_count": 0,
                "top3_count": 0,
                "top10_count": 0,
            },
        }

    cfg = PipelineSettings(
        input_path=Path("live"),
        output_dir=Path("live"),
        cache_dir=Path("live"),
    )
    top_all, top10, top3 = build_municipality_rankings(df, cfg)
    municipalities = top_all["муниципалитет"].tolist() if not top_all.empty else []
    topics_df, groups_df, reasons_df = build_topic_group_breakdown(df, municipalities, cfg)
    top10 = attach_reasons_to_rankings(top10, reasons_df)
    top3 = attach_reasons_to_rankings(top3, reasons_df)
    top_all = attach_reasons_to_rankings(top_all, reasons_df)

    period_start, period_end = compute_incident_date_range(df)
    n_prob = int((df["severity"] > 0).sum()) if "severity" in df.columns else 0
    n_muni = int(df["муниципалитет"].nunique()) if "муниципалитет" in df.columns else 0
    stats = {
        "rows_processed": len(df),
        "problem_count": n_prob,
        "municipality_count": n_muni,
        "top3_count": len(top3),
        "top10_count": len(top10),
    }
    if period_start is not None:
        stats["start_date"] = period_start.strftime("%Y-%m-%d")
    if period_end is not None:
        stats["end_date"] = period_end.strftime("%Y-%m-%d")

    summary_text = (
        f"Live-поток граждан: {len(df)} обращений"
        f"{f', {n_prob} проблемных' if n_prob else ''}"
        f"{f', {n_muni} муниципалитетов' if n_muni else ''}."
    )

    return {
        "summary_text": summary_text,
        "top3": _df_to_records(top3),
        "top10": _df_to_records(top10),
        "all": _df_to_records(top_all),
        "topics": _df_to_records(topics_df),
        "groups": _df_to_records(groups_df),
        "reasons": _df_to_records(reasons_df),
        "severity_breakdown": build_severity_breakdown(df),
        "resolved_stats": build_resolved_stats(df),
        "stats": stats,
    }
