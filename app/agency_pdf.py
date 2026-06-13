"""PDF-отчёт для ведомства по муниципалитету."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from reportlab.lib.units import mm
from reportlab.platypus import Spacer, Table, TableStyle

from app.agency_mapping import region_name
from app.agency_summary import GroupStat, TopicStat
from app.pdf_report import (
    CONTENT_W,
    _build_pdf,
    _para,
    _section_heading,
    _severity_chart,
    _styles,
    _table_base,
)
from app.report import SEVERITY_LABELS
from schemas import SeverityStat


@dataclass
class AgencyReportContext:
    municipality: str
    agency: str
    period_start: str | None
    period_end: str | None
    counts: dict[int, int]
    top_topics: list[TopicStat] = field(default_factory=list)
    top_groups: list[GroupStat] = field(default_factory=list)
    critical_examples: list[dict] = field(default_factory=list)
    priority: str = "НИЗКИЙ"
    total: int = 0
    critical_total: int = 0
    avg_severity: float = 0.0
    recommendations: list[str] = field(default_factory=list)
    contact_email: str | None = None
    admin_contact_name: str | None = None
    admin_contact_email: str | None = None
    admin_contact_phone: str | None = None
    source_groups: list[str] = field(default_factory=list)


def contact_summary_rows(ctx: AgencyReportContext) -> list[tuple[str, str]]:
    """Строки контактов ведомства и администрации МО для PDF/Excel."""
    rows: list[tuple[str, str]] = []
    if ctx.contact_email:
        rows.append(("Email ведомства", ctx.contact_email))
    if ctx.admin_contact_name:
        rows.append(("Администрация МО", ctx.admin_contact_name))
    if ctx.admin_contact_email:
        rows.append(("Email МО", ctx.admin_contact_email))
    if ctx.admin_contact_phone:
        rows.append(("Телефон МО", ctx.admin_contact_phone))
    return rows


def _format_period(start: str | None, end: str | None) -> str:
    if start and end:
        return f"{start} — {end}"
    if start:
        return f"с {start}"
    if end:
        return f"по {end}"
    return "период не указан"


def _summary_text(ctx: AgencyReportContext) -> str:
    if ctx.total == 0:
        return (
            f"По муниципалитету «{ctx.municipality}» в зоне ответственности "
            f"«{ctx.agency}» за указанный период проблемных обращений не зафиксировано."
        )
    high_pct = round(100 * ctx.critical_total / ctx.total) if ctx.total else 0
    groups_hint = ""
    if ctx.source_groups:
        groups_hint = f" Группы тем: {', '.join(ctx.source_groups[:4])}"
        if len(ctx.source_groups) > 4:
            groups_hint += " и др."
    return (
        f"В муниципалитете «{ctx.municipality}» по направлению «{ctx.agency}» "
        f"за период {_format_period(ctx.period_start, ctx.period_end)} "
        f"учтено {ctx.total} проблемных обращений (классы 1–4, класс 0 не учитывается). "
        f"Приоритет: {ctx.priority}. Критичные (классы 3–4): {ctx.critical_total} ({high_pct}%). "
        f"Средняя тяжесть: {ctx.avg_severity:.2f}.{groups_hint} "
        f"Детализация — в таблицах ниже; перечень обращений классов 3–4 — в incidents.xlsx."
    )


def _kpi_table(ctx: AgencyReportContext, styles: dict) -> Table:
    rows = [
        [_para("Показатель", styles["table_cell"]), _para("Значение", styles["table_cell_center"])],
        [_para("Всего проблемных", styles["table_cell"]), _para(str(ctx.total), styles["table_cell_center"])],
        [_para("Критичные (3–4)", styles["table_cell"]), _para(str(ctx.critical_total), styles["table_cell_center"])],
        [_para("Средняя тяжесть", styles["table_cell"]), _para(f"{ctx.avg_severity:.2f}", styles["table_cell_center"])],
        [_para("Приоритет", styles["table_cell"]), _para(ctx.priority, styles["table_cell_center"])],
    ]
    table = Table(rows, colWidths=[55 * mm, CONTENT_W - 55 * mm])
    table.setStyle(TableStyle(_table_base(header=True)))
    return table


def _examples_section(ctx: AgencyReportContext, styles: dict) -> list:
    if not ctx.critical_examples:
        return []
    flow: list = [
        _section_heading("Примеры критичных обращений", styles),
        Spacer(1, 2 * mm),
    ]
    for i, ex in enumerate(ctx.critical_examples[:5], start=1):
        header = f"{i}. [{ex.get('label', '')}]"
        if ex.get("topic"):
            header += f" · {ex['topic']}"
        if ex.get("date"):
            header += f" · {ex['date']}"
        flow.append(_para(header, styles["table_cell"]))
        flow.append(_para(str(ex.get("text", "")), styles["body"]))
        flow.append(Spacer(1, 2 * mm))
    return flow


def build_agency_pdf(ctx: AgencyReportContext) -> bytes:
    styles = _styles()
    story: list = []

    story.append(_para("ZeroProblems", styles["brand"]))
    story.append(Spacer(1, 2 * mm))
    story.append(_para("Отчёт для ведомства", styles["title"]))
    story.append(_para(ctx.agency, styles["subtitle"]))
    story.append(Spacer(1, 2 * mm))
    story.append(_para(f"Приоритет отработки: {ctx.priority}", styles["subtitle"]))
    story.append(Spacer(1, 3 * mm))

    meta_rows = [
        [_para("Регион", styles["table_cell"]), _para(region_name(), styles["table_cell"])],
        [_para("Муниципалитет", styles["table_cell"]), _para(ctx.municipality, styles["table_cell"])],
        [_para("Период", styles["table_cell"]), _para(_format_period(ctx.period_start, ctx.period_end), styles["table_cell"])],
        [
            _para("Дата формирования", styles["table_cell"]),
            _para(datetime.now().strftime("%d.%m.%Y %H:%M"), styles["table_cell"]),
        ],
    ]
    for label, value in contact_summary_rows(ctx):
        meta_rows.append([_para(label, styles["table_cell"]), _para(value, styles["table_cell"])])
    meta_table = Table(meta_rows, colWidths=[38 * mm, CONTENT_W - 38 * mm])
    meta_table.setStyle(TableStyle(_table_base(zebra=False)))
    story.append(meta_table)
    story.append(Spacer(1, 5 * mm))

    story.append(_section_heading("Сводка", styles))
    story.append(Spacer(1, 2 * mm))
    story.append(_para(_summary_text(ctx), styles["body"]))
    story.append(Spacer(1, 4 * mm))
    story.append(_kpi_table(ctx, styles))
    story.append(Spacer(1, 5 * mm))

    counts_rows = [
        [_para("Класс", styles["table_cell"]), _para("Уровень", styles["table_cell"]), _para("Кол-во", styles["table_cell_center"])],
    ]
    for sev in (4, 3, 2, 1):
        counts_rows.append(
            [
                _para(str(sev), styles["table_cell_center"]),
                _para(SEVERITY_LABELS[sev], styles["table_cell"]),
                _para(str(ctx.counts.get(sev, 0)), styles["table_cell_center"]),
            ]
        )
    counts_table = Table(counts_rows, colWidths=[18 * mm, 55 * mm, CONTENT_W - 73 * mm])
    style = _table_base(header=True)
    style.append(("ALIGN", (0, 0), (0, -1), "CENTER"))
    style.append(("ALIGN", (2, 0), (2, -1), "CENTER"))
    counts_table.setStyle(TableStyle(style))
    story.append(_section_heading("Распределение по классам", styles))
    story.append(Spacer(1, 2 * mm))
    story.append(counts_table)
    story.append(Spacer(1, 4 * mm))

    total_sev = ctx.total or 1
    severity_stats = [
        SeverityStat(
            severity=sev,
            label=SEVERITY_LABELS[sev],
            count=ctx.counts.get(sev, 0),
            percentage=round(100 * ctx.counts.get(sev, 0) / total_sev, 1),
        )
        for sev in range(1, 5)
    ]
    chart = _severity_chart(severity_stats, CONTENT_W / mm)
    if chart is not None:
        story.append(chart)
        story.append(Spacer(1, 4 * mm))

    if ctx.top_groups:
        story.append(_section_heading("Группы тем", styles))
        story.append(Spacer(1, 2 * mm))
        g_rows = [
            [_para("Группа", styles["table_cell"]), _para("Доля", styles["table_cell_center"]), _para("Шт.", styles["table_cell_center"])],
        ]
        for g in ctx.top_groups[:8]:
            g_rows.append(
                [
                    _para(g.name, styles["table_cell"]),
                    _para(f"{g.percentage}%", styles["table_cell_center"]),
                    _para(str(g.count), styles["table_cell_center"]),
                ]
            )
        g_table = Table(g_rows, colWidths=[CONTENT_W - 40 * mm, 20 * mm, 20 * mm])
        g_style = _table_base(header=True)
        g_style.append(("ALIGN", (1, 0), (-1, -1), "CENTER"))
        g_table.setStyle(TableStyle(g_style))
        story.append(g_table)
        story.append(Spacer(1, 4 * mm))

    if ctx.top_topics:
        story.append(_section_heading("Основные темы", styles))
        story.append(Spacer(1, 2 * mm))
        topic_rows = [
            [
                _para("Тема", styles["table_cell"]),
                _para("%", styles["table_cell_center"]),
                _para("Шт.", styles["table_cell_center"]),
                _para("Ср.тяж.", styles["table_cell_center"]),
                _para("3–4", styles["table_cell_center"]),
            ],
        ]
        for t in ctx.top_topics[:10]:
            topic_rows.append(
                [
                    _para(t.name, styles["table_cell"]),
                    _para(f"{t.percentage}", styles["table_cell_center"]),
                    _para(str(t.count), styles["table_cell_center"]),
                    _para(f"{t.avg_severity:.1f}", styles["table_cell_center"]),
                    _para(str(t.critical_count), styles["table_cell_center"]),
                ]
            )
        topics_table = Table(
            topic_rows,
            colWidths=[CONTENT_W - 58 * mm, 14 * mm, 14 * mm, 15 * mm, 15 * mm],
        )
        t_style = _table_base(header=True)
        t_style.append(("ALIGN", (1, 0), (-1, -1), "CENTER"))
        topics_table.setStyle(TableStyle(t_style))
        story.append(topics_table)
        story.append(Spacer(1, 4 * mm))

    story.extend(_examples_section(ctx, styles))

    if ctx.recommendations:
        story.append(_section_heading("Рекомендации", styles))
        story.append(Spacer(1, 2 * mm))
        for i, rec in enumerate(ctx.recommendations, start=1):
            story.append(_para(f"{i}. {rec}", styles["body"]))
            story.append(Spacer(1, 1.5 * mm))

    story.append(Spacer(1, 4 * mm))
    story.append(
        _para(
            "Методика: автоматическая классификация ONNX (XLM-RoBERTa), классы 0–4. "
            "Отчёт сформирован системой ZeroProblems на основе обращений граждан.",
            styles["table_cell"],
        )
    )

    title = f"Отчёт — {ctx.agency} — {ctx.municipality}"
    return _build_pdf(story, title)
