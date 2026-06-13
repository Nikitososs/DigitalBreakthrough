"""Сборка Excel-отчётов (полный и Top-10) из DataFrame и из report.json."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.config.settings import PipelineSettings
from app.excel_format import ExcelReportPayload, build_styled_workbook
from app.io import read_labeled_parquet, select_labeled_columns
from app.report import build_resolved_stats, build_severity_breakdown, build_unresolved_topics_groups


def _report_summary_message(report: dict | None) -> str:
    if not report:
        return "Нет данных"
    text = str(report.get("summary_text") or "Нет данных").strip()
    return text or "Нет данных"


def _read_optional_xlsx(path: Path) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    try:
        df = pd.read_excel(path, engine="openpyxl")
        return df if not df.empty else None
    except Exception:
        return None


def _labeled_parquet_path(output_dir: Path) -> Path | None:
    """cache/jobs/{id}/output → cache/jobs/{id}/cache/labeled.parquet"""
    candidate = output_dir.parent / "cache" / "labeled.parquet"
    return candidate if candidate.is_file() else None


def _load_labeled_sample(output_dir: Path) -> pd.DataFrame | None:
    parquet = _labeled_parquet_path(output_dir)
    if parquet is None:
        return None
    try:
        labeled = read_labeled_parquet(parquet)
        if labeled.empty:
            return None
        return select_labeled_columns(labeled).head(5000)
    except Exception:
        return None


def _load_full_labeled(output_dir: Path) -> pd.DataFrame | None:
    parquet = _labeled_parquet_path(output_dir)
    if parquet is None:
        return None
    try:
        labeled = read_labeled_parquet(parquet)
        return labeled if not labeled.empty else None
    except Exception:
        return None


def _filter_resolved_stats(resolved_stats: list[dict], top_names: set[str]) -> list[dict]:
    if not top_names:
        return []
    return [row for row in resolved_stats if str(row.get("муниципалитет", "")) in top_names]


def _apply_unresolved_from_labeled(
    payload: ExcelReportPayload,
    labeled: pd.DataFrame,
) -> ExcelReportPayload:
    if labeled is None or labeled.empty:
        return payload

    payload.severity_breakdown = build_severity_breakdown(labeled)
    payload.resolved_stats = build_resolved_stats(labeled)
    topics, groups = build_unresolved_topics_groups(labeled)
    if not topics.empty:
        if not payload.include_all_municipalities and not payload.top10.empty:
            top_names = _top10_municipality_names(payload.top10)
            topics = topics[topics["муниципалитет"].astype(str).isin(top_names)].copy()
            groups = groups[groups["муниципалитет"].astype(str).isin(top_names)].copy()
        payload.topics_df = topics
        payload.groups_df = groups
    return payload


def _apply_unresolved_export_stats(payload: ExcelReportPayload, output_dir: Path) -> ExcelReportPayload:
    labeled = _load_full_labeled(output_dir)
    if labeled is None:
        return payload
    return _apply_unresolved_from_labeled(payload, labeled)


def _meta_rows_from_output_dir(output_dir: Path) -> list[tuple[str, str]] | None:
    rows: list[tuple[str, str]] = []
    job_dir = output_dir.parent
    input_path = job_dir / "input.xlsx"
    if input_path.is_file():
        rows.append(("input", str(input_path)))

    summary_path = output_dir / "summary.json"
    if summary_path.is_file():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            model = summary.get("model")
            if model:
                rows.append(("summary", f"ollama/{model}"))
            if summary.get("generated_at"):
                rows.append(("summary_generated", str(summary["generated_at"])))
        except Exception:
            pass

    return rows or None


def _top10_municipality_names(top10: pd.DataFrame) -> set[str]:
    if top10.empty or "муниципалитет" not in top10.columns:
        return set()
    return set(top10["муниципалитет"].astype(str))


def _filter_for_top10(
    top10: pd.DataFrame,
    topics_df: pd.DataFrame,
    groups_df: pd.DataFrame,
    reasons_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    top_names = _top10_municipality_names(top10)
    if not top_names:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    def _filter(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "муниципалитет" not in df.columns:
            return pd.DataFrame()
        return df[df["муниципалитет"].astype(str).isin(top_names)].copy()

    return _filter(topics_df), _filter(groups_df), _filter(reasons_df)


def _enrich_payload_from_disk(
    payload: ExcelReportPayload,
    output_dir: Path,
    *,
    include_labeled: bool,
    top10_only: bool,
) -> ExcelReportPayload:
    if top10_only:
        topics, groups, reasons = _filter_for_top10(
            payload.top10, payload.topics_df, payload.groups_df, payload.reasons_df
        )
        payload.topics_df = topics
        payload.groups_df = groups
        payload.reasons_df = reasons
    else:
        if payload.muni_summaries is None:
            payload.muni_summaries = _read_optional_xlsx(output_dir / "top10_summaries.xlsx")
            if payload.muni_summaries is None:
                payload.muni_summaries = _read_optional_xlsx(output_dir / "municipality_summaries.xlsx")
        if payload.top3_summaries is None:
            payload.top3_summaries = _read_optional_xlsx(output_dir / "top3_summaries.xlsx")
        if include_labeled and payload.labeled_sample is None:
            payload.labeled_sample = _load_labeled_sample(output_dir)
            payload.include_labeled_sample = payload.labeled_sample is not None

    if payload.meta_rows is None:
        payload.meta_rows = _meta_rows_from_output_dir(output_dir)

    payload = _apply_unresolved_export_stats(payload, output_dir)
    if top10_only:
        top_names = _top10_municipality_names(payload.top10)
        payload.resolved_stats = _filter_resolved_stats(payload.resolved_stats, top_names)
    return payload


def _payload_from_report(report: dict, **kwargs) -> ExcelReportPayload:
    stats = report.get("stats") or {}
    return ExcelReportPayload(
        summary_text=_report_summary_message(report),
        stats=stats if isinstance(stats, dict) else {},
        top_all=pd.DataFrame(report.get("all") or []),
        top10=pd.DataFrame(report.get("top10") or []),
        top3=pd.DataFrame(report.get("top3") or []),
        topics_df=pd.DataFrame(report.get("topics") or []),
        groups_df=pd.DataFrame(report.get("groups") or []),
        reasons_df=pd.DataFrame(report.get("reasons") or []),
        severity_breakdown=list(report.get("severity_breakdown") or []),
        resolved_stats=list(report.get("resolved_stats") or []),
        **kwargs,
    )


def _save_workbook(wb, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def write_excel_report(
    cfg: PipelineSettings,
    top_all: pd.DataFrame,
    top10: pd.DataFrame,
    top3: pd.DataFrame,
    topics_df: pd.DataFrame,
    groups_df: pd.DataFrame,
    reasons_df: pd.DataFrame | None = None,
    labeled_df: pd.DataFrame | None = None,
    muni_summaries: pd.DataFrame | None = None,
    top3_summaries: pd.DataFrame | None = None,
    *,
    summary_text: str = "",
    stats: dict | None = None,
    severity_breakdown: list[dict] | None = None,
) -> Path:
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = cfg.output_dir / "report_top_districts.xlsx"

    labeled_sample = None
    if labeled_df is not None and not labeled_df.empty:
        labeled_sample = select_labeled_columns(labeled_df).head(5000)

    export_topics = topics_df
    export_groups = groups_df
    export_severity = severity_breakdown or []
    export_resolved: list[dict] = []
    if labeled_df is not None and not labeled_df.empty:
        export_severity = build_severity_breakdown(labeled_df)
        export_resolved = build_resolved_stats(labeled_df)
        ut, ug = build_unresolved_topics_groups(labeled_df)
        if not ut.empty:
            export_topics = ut
            export_groups = ug

    payload = ExcelReportPayload(
        summary_text=summary_text,
        stats=stats or {},
        top_all=top_all,
        top10=top10,
        top3=top3,
        topics_df=export_topics,
        groups_df=export_groups,
        reasons_df=reasons_df if reasons_df is not None else pd.DataFrame(),
        severity_breakdown=export_severity,
        resolved_stats=export_resolved,
        muni_summaries=muni_summaries,
        top3_summaries=top3_summaries,
        labeled_sample=labeled_sample,
        include_all_municipalities=True,
        include_labeled_sample=labeled_sample is not None,
        meta_rows=[
            ("input", str(cfg.input_path)),
            ("classifier", "onnx/xlm-roberta"),
            ("summary", f"ollama/{cfg.ollama_model}"),
            ("top_hotspots", str(cfg.top_hotspots)),
            ("top_municipalities", str(cfg.top_municipalities)),
        ],
    )
    _save_workbook(build_styled_workbook(payload), out_path)

    write_top10_excel(
        cfg.output_dir,
        top10=top10,
        top3=top3,
        topics_df=export_topics,
        groups_df=export_groups,
        reasons_df=reasons_df,
        muni_summaries=muni_summaries,
        top3_summaries=top3_summaries,
        summary_text=summary_text,
        stats=stats,
        severity_breakdown=export_severity,
        resolved_stats=export_resolved,
    )
    return out_path


def write_top10_excel(
    output_dir: Path,
    *,
    top10: pd.DataFrame,
    top3: pd.DataFrame,
    topics_df: pd.DataFrame,
    groups_df: pd.DataFrame,
    reasons_df: pd.DataFrame | None = None,
    muni_summaries: pd.DataFrame | None = None,
    top3_summaries: pd.DataFrame | None = None,
    placeholder_message: str = "Нет данных",
    summary_text: str = "",
    stats: dict | None = None,
    severity_breakdown: list[dict] | None = None,
    resolved_stats: list[dict] | None = None,
) -> Path:
    """Excel по Top-10: сводка, рейтинг, темы, причины, графики."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "report_top10.xlsx"

    top_names: set[str] = set()
    if not top10.empty and "муниципалитет" in top10.columns:
        top_names = set(top10["муниципалитет"].astype(str))

    reasons_top = (
        reasons_df[reasons_df["муниципалитет"].astype(str).isin(top_names)].copy()
        if reasons_df is not None and not reasons_df.empty and top_names
        else pd.DataFrame()
    )
    topics_top = (
        topics_df[topics_df["муниципалитет"].astype(str).isin(top_names)].copy()
        if not topics_df.empty and top_names
        else pd.DataFrame()
    )
    groups_top = (
        groups_df[groups_df["муниципалитет"].astype(str).isin(top_names)].copy()
        if not groups_df.empty and top_names
        else pd.DataFrame()
    )
    resolved_top = _filter_resolved_stats(resolved_stats or [], top_names)

    payload = ExcelReportPayload(
        summary_text=summary_text or placeholder_message,
        stats=stats or {},
        top_all=pd.DataFrame(),
        top10=top10,
        top3=top3,
        topics_df=topics_top,
        groups_df=groups_top,
        reasons_df=reasons_top,
        severity_breakdown=severity_breakdown or [],
        resolved_stats=resolved_top,
        muni_summaries=muni_summaries,
        top3_summaries=top3_summaries,
        include_all_municipalities=False,
    )
    _save_workbook(build_styled_workbook(payload), out_path)
    return out_path


def build_top10_excel_from_report(report: dict, output_dir: Path) -> Path:
    """Собрать Top-10 Excel из report.json (актуальный стиль, перезапись файла)."""
    payload = _payload_from_report(
        report,
        include_all_municipalities=False,
        muni_summaries=_read_optional_xlsx(output_dir / "top10_summaries.xlsx")
        or _read_optional_xlsx(output_dir / "municipality_summaries.xlsx"),
        top3_summaries=_read_optional_xlsx(output_dir / "top3_summaries.xlsx"),
    )
    payload = _enrich_payload_from_disk(payload, output_dir, include_labeled=False, top10_only=True)
    out_path = output_dir / "report_top10.xlsx"
    output_dir.mkdir(parents=True, exist_ok=True)
    return _save_workbook(build_styled_workbook(payload), out_path)


def build_full_excel_from_report(report: dict, output_dir: Path) -> Path:
    """Собрать полный Excel (все МО) из report.json (актуальный стиль, перезапись файла)."""
    payload = _payload_from_report(report, include_all_municipalities=True)
    payload = _enrich_payload_from_disk(payload, output_dir, include_labeled=True, top10_only=False)
    out_path = output_dir / "report_top_districts.xlsx"
    output_dir.mkdir(parents=True, exist_ok=True)
    return _save_workbook(build_styled_workbook(payload), out_path)
