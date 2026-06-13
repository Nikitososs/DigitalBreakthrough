"""ZIP-архив отчётов для ведомств по муниципалитетам."""

from __future__ import annotations

import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pandas as pd

from app.agency_mapping import (
    resolve_agency,
    resolve_agency_email,
    resolve_municipality_admin,
    safe_path_segment,
)
from app.agency_pdf import AgencyReportContext, build_agency_pdf, contact_summary_rows
from app.agency_summary import (
    build_recommendations,
    critical_examples,
    priority_level,
    top_groups_stats,
    top_topics_stats,
)
from app.report import SEVERITY_LABELS
from app.report_dates import DATE_COLUMN, _parse_date_column, compute_incident_date_range
from app.resolved import filter_unresolved

ProgressCallback = Callable[[int, int, str, str, str], None]

EXCEL_COLUMNS = [
    ("дата_создания", "Дата создания"),
    ("severity", "Класс"),
    ("Уровень_тяжести", "Уровень тяжести"),
    ("группа", "Группа тем"),
    ("тема", "Тема"),
    ("муниципалитет", "Муниципалитет"),
    ("текст", "Текст обращения"),
    ("row_id", "ID"),
]

ZIP_README = """ZeroProblems — архив отчётов для ведомств
================================================

Структура:
  {Муниципалитет}/{Ведомство}/report.pdf   — аналитический отчёт
  {Муниципалитет}/{Ведомство}/incidents.xlsx — обращения (листы: Сводка, Критические_3_4, Все_1_4)

Классы тяжести ONNX: 0 — не инцидент; 1–4 — проблемные (в отчётах учитываются 1–4).
Приоритет в PDF: КРИТИЧЕСКИЙ / ВЫСОКИЙ / СРЕДНИЙ / НИЗКИЙ — по числу обращений классов 3–4.

Контакты (в шапке report.pdf и на листе «Сводка» incidents.xlsx):
  Email ведомства — региональное министерство по группе тем;
  Администрация МО, Email МО, Телефон МО — местная администрация муниципалитета.
"""


def _attach_agency(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "группа" not in out.columns:
        out["группа"] = ""
    out["ведомство"] = out["группа"].map(lambda g: resolve_agency(str(g)))
    return out


def _severity_counts(sub: pd.DataFrame) -> dict[int, int]:
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    if sub.empty or "severity" not in sub.columns:
        return counts
    for sev in counts:
        counts[sev] = int((sub["severity"] == sev).sum())
    return counts


def _format_date(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    text = str(value).strip()
    return text[:10] if text else None


def _export_frame(rows: pd.DataFrame) -> pd.DataFrame:
    export = rows.copy()
    if "severity" in export.columns:
        def _severity_label(value):
            try:
                return SEVERITY_LABELS.get(int(value), value)
            except (TypeError, ValueError):
                return value

        export["severity"] = export["severity"].map(_severity_label)
    cols = [c for c, _ in EXCEL_COLUMNS if c in export.columns]
    headers = {c: h for c, h in EXCEL_COLUMNS if c in export.columns}
    return export[cols].rename(columns=headers)


def _summary_sheet_rows(ctx: AgencyReportContext) -> pd.DataFrame:
    rows = [
        ("Регион", "Омская область"),
        ("Муниципалитет", ctx.municipality),
        ("Ведомство", ctx.agency),
        ("Период", f"{ctx.period_start or '—'} — {ctx.period_end or '—'}"),
        ("Приоритет", ctx.priority),
        ("Всего проблемных (1–4)", str(ctx.total)),
        ("Критичные (3–4)", str(ctx.critical_total)),
        ("Средняя тяжесть", f"{ctx.avg_severity:.2f}"),
    ]
    for sev in (4, 3, 2, 1):
        rows.append((f"Класс {sev}", str(ctx.counts.get(sev, 0))))
    if ctx.top_topics:
        top = ctx.top_topics[0]
        rows.append(("Топ-тема", f"{top.name} ({top.count} шт.)"))
    rows.extend(contact_summary_rows(ctx))
    if ctx.recommendations:
        rows.append(("Рекомендация 1", ctx.recommendations[0]))
    return pd.DataFrame(rows, columns=["Показатель", "Значение"])


def _build_excel_bytes(ctx: AgencyReportContext, agency_df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    critical = agency_df[agency_df["severity"].isin([3, 4])] if "severity" in agency_df.columns else agency_df
    critical = _sort_by_date(critical)

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _summary_sheet_rows(ctx).to_excel(writer, sheet_name="Сводка", index=False)
        _export_frame(critical).to_excel(writer, sheet_name="Критические_3_4", index=False)
        _export_frame(_sort_by_date(agency_df)).to_excel(writer, sheet_name="Все_1_4", index=False)
    return buffer.getvalue()


@dataclass
class AgencyWorkItem:
    municipality: str
    agency: str
    agency_df: pd.DataFrame


def _prepare_problems(labeled_df: pd.DataFrame) -> pd.DataFrame:
    if labeled_df is None or labeled_df.empty:
        raise ValueError("Нет данных для формирования отчётов")

    df = _attach_agency(labeled_df)
    if "муниципалитет" not in df.columns:
        raise ValueError("В данных отсутствует колонка «муниципалитет»")
    if "severity" not in df.columns:
        raise ValueError("В данных отсутствует колонка «severity»")

    problems = df[df["severity"].isin([1, 2, 3, 4])].copy()
    problems = filter_unresolved(problems)
    if problems.empty:
        raise ValueError("Нет нерешённых проблемных обращений (классы 1–4)")
    return problems


def _iter_work_items(problems: pd.DataFrame) -> list[AgencyWorkItem]:
    items: list[AgencyWorkItem] = []
    for muni, muni_df in problems.groupby("муниципалитет", sort=True):
        muni_name = str(muni).strip()
        for agency, agency_df in muni_df.groupby("ведомство", sort=True):
            agency_name = str(agency).strip()
            if agency_df.empty:
                continue
            items.append(
                AgencyWorkItem(
                    municipality=muni_name,
                    agency=agency_name,
                    agency_df=agency_df,
                )
            )
    return items


def _build_context(
    item: AgencyWorkItem,
    *,
    period_start_s: str | None,
    period_end_s: str | None,
) -> AgencyReportContext:
    counts = _severity_counts(item.agency_df)
    total = sum(counts.values())
    critical_total = counts[3] + counts[4]
    avg = float(item.agency_df["severity"].mean()) if total else 0.0
    topics = top_topics_stats(item.agency_df)
    groups = top_groups_stats(item.agency_df)
    priority = priority_level(counts)
    source_groups = sorted(
        {str(g).strip() for g in item.agency_df.get("группа", pd.Series(dtype=str)).astype(str) if str(g).strip()}
    )
    recs = build_recommendations(
        municipality=item.municipality,
        agency=item.agency,
        priority=priority,
        counts=counts,
        topics=topics,
        critical_total=critical_total,
    )
    admin = resolve_municipality_admin(item.municipality)
    return AgencyReportContext(
        municipality=item.municipality,
        agency=item.agency,
        period_start=period_start_s,
        period_end=period_end_s,
        counts=counts,
        top_topics=topics,
        top_groups=groups,
        critical_examples=critical_examples(item.agency_df),
        priority=priority,
        total=total,
        critical_total=critical_total,
        avg_severity=round(avg, 2),
        recommendations=recs,
        contact_email=resolve_agency_email(item.agency),
        admin_contact_name=admin.get("administration"),
        admin_contact_email=admin.get("email"),
        admin_contact_phone=admin.get("phone"),
        source_groups=source_groups,
    )


def build_department_preview(labeled_df: pd.DataFrame) -> dict[str, Any]:
    problems = _prepare_problems(labeled_df)
    period_start, period_end = compute_incident_date_range(problems)

    municipalities: list[dict[str, Any]] = []
    agencies_count = 0

    for muni, muni_df in problems.groupby("муниципалитет", sort=True):
        muni_name = str(muni).strip()
        agencies: list[dict[str, Any]] = []
        for agency, agency_df in muni_df.groupby("ведомство", sort=True):
            agency_name = str(agency).strip()
            if agency_df.empty:
                continue
            counts = _severity_counts(agency_df)
            critical = counts[3] + counts[4]
            total = sum(counts.values())
            topics = top_topics_stats(agency_df, limit=1)
            agencies.append(
                {
                    "name": agency_name,
                    "total_count": total,
                    "critical_count": critical,
                    "counts": {str(k): v for k, v in counts.items()},
                    "top_topic": topics[0].name if topics else None,
                    "priority": priority_level(counts),
                    "contact_email": resolve_agency_email(agency_name),
                }
            )
            agencies_count += 1
        if agencies:
            admin = resolve_municipality_admin(muni_name)
            municipalities.append(
                {
                    "name": muni_name,
                    "agencies": agencies,
                    "administration": admin.get("administration"),
                    "admin_contact_email": admin.get("email"),
                    "admin_contact_phone": admin.get("phone"),
                    "admin_website": admin.get("website"),
                    "admin_contact_verified": admin.get("contact_verified", False),
                }
            )

    return {
        "municipalities_count": len(municipalities),
        "agencies_count": agencies_count,
        "reports_count": agencies_count,
        "period_start": _format_date(period_start),
        "period_end": _format_date(period_end),
        "municipalities": municipalities,
    }


def _sort_by_date(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if DATE_COLUMN not in df.columns:
        return df
    out = df.copy()
    out["_sort_date"] = _parse_date_column(out[DATE_COLUMN])
    out = out.sort_values("_sort_date", ascending=True, na_position="last").drop(columns=["_sort_date"])
    return out


def build_department_reports_zip(
    labeled_df: pd.DataFrame,
    *,
    on_progress: ProgressCallback | None = None,
) -> bytes:
    """Формирует ZIP: README + {МО}/{ведомство}/report.pdf + incidents.xlsx."""
    problems = _prepare_problems(labeled_df)
    work_items = _iter_work_items(problems)
    if not work_items:
        raise ValueError("Нет отчётов для формирования")

    period_start, period_end = compute_incident_date_range(problems)
    period_start_s = _format_date(period_start)
    period_end_s = _format_date(period_end)
    total = len(work_items)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", ZIP_README)

        for idx, item in enumerate(work_items, start=1):
            if on_progress:
                on_progress(idx, total, item.municipality, item.agency, "pdf")
            muni_dir = safe_path_segment(item.municipality)
            agency_dir = safe_path_segment(item.agency)
            base = f"{muni_dir}/{agency_dir}/"

            ctx = _build_context(item, period_start_s=period_start_s, period_end_s=period_end_s)
            pdf_bytes = build_agency_pdf(ctx)
            zf.writestr(f"{base}report.pdf", pdf_bytes)

            if on_progress:
                on_progress(idx, total, item.municipality, item.agency, "excel")
            excel_bytes = _build_excel_bytes(ctx, item.agency_df)
            zf.writestr(f"{base}incidents.xlsx", excel_bytes)

        if on_progress:
            on_progress(total, total, "", "", "archive")

    return buffer.getvalue()
