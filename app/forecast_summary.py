"""LLM-сводка по экрану «Прогноз»: все графики и тренды в одном докладе."""

from __future__ import annotations

from app.config.llm import OLLAMA_MODEL
from app.config.paths import DATA_DIR
from app.config.settings import PipelineSettings
from app.summary import _chat


def _fmt_volume(items: list[dict] | None, limit: int = 8) -> str:
    if not items:
        return "нет данных"
    lines = []
    for row in items[:limit]:
        label = str(row.get("label", "")).strip()
        value = row.get("value", 0)
        share = row.get("share_pct")
        if share is not None:
            lines.append(f"- {label}: {value} ({share}%)")
        else:
            lines.append(f"- {label}: {value}")
    return "\n".join(lines)


def _fmt_trends(items: list[dict] | None, limit: int = 8) -> str:
    if not items:
        return "нет выраженных изменений"
    lines = []
    for row in items[:limit]:
        label = str(row.get("label", "")).strip()
        trend = row.get("trend_pct", 0)
        nxt = row.get("forecast_next_week")
        risk = row.get("risk_level", "")
        total = row.get("history_total")
        parts = [f"{label}: тренд {trend:+.0f}%"]
        if nxt is not None:
            parts.append(f"прогноз ~{round(float(nxt))}/нед")
        if total is not None:
            parts.append(f"в истории {int(total)}")
        if risk:
            parts.append(f"риск {risk}")
        lines.append("- " + ", ".join(parts))
    return "\n".join(lines)


def _fmt_severity(items: list[dict] | None) -> str:
    if not items:
        return "нет данных"
    return ", ".join(
        f"класс {row.get('severity', row.get('label', '?'))}: {row.get('count', 0)}"
        for row in items
    )


def _fmt_monthly(items: list[dict] | None, tail: int = 6) -> str:
    if not items:
        return "нет данных"
    recent = items[-tail:]
    return ", ".join(
        f"{str(row.get('period', ''))[:7]}: {row.get('count', 0)}"
        for row in recent
    )


def build_forecast_context(forecast: dict) -> str:
    """Структурированный контекст для LLM из payload прогноза."""
    horizon = forecast.get("horizon_weeks", 4)
    kpis = forecast.get("kpis") or {}
    region = forecast.get("region_chart") or forecast.get("region_series") or {}
    critical = forecast.get("critical_chart") or {}
    processing = forecast.get("processing") or {}
    quality = forecast.get("data_quality") or {}

    blocks: list[str] = [
        f"Горизонт прогноза: {horizon} нед.",
        f"Обращений в выборке: {forecast.get('incident_count', 0)}.",
        f"Загрузок в архиве: {forecast.get('jobs_count', 0)}.",
        f"Период данных: {kpis.get('date_from') or '—'} — {kpis.get('date_to') or '—'}.",
        "",
        "=== Регион (недельный тренд) ===",
        f"Тренд: {region.get('trend_pct', 0):+.1f}%, риск: {region.get('risk_level', '—')}.",
        f"Среднее за 12 нед.: {kpis.get('avg_weekly_12w', 0)}, прогноз ~{kpis.get('forecast_avg_weekly', 0)}/нед.",
        f"Сумма прогноза на {horizon} нед.: {kpis.get('forecast_total', 0)}.",
        f"След. неделя ~{region.get('forecast_next_week', '—')}, прошлая неделя факт {region.get('last_week_actual', '—')}.",
        f"Пик: {kpis.get('peak_week_count', '—')} ({kpis.get('peak_week_date', '—')}).",
        f"Краткая автосводка: {forecast.get('summary_text', '')}",
        "",
        "=== Критичные обращения (классы 3–4) ===",
        f"Тренд: {critical.get('trend_pct', 0):+.1f}%, риск: {critical.get('risk_level', '—')}.",
        f"Прогноз след. нед.: {critical.get('forecast_next_week', '—')}.",
        "",
        "=== Помесячная динамика (последние месяцы) ===",
        _fmt_monthly(forecast.get("monthly_series")),
        "",
        "=== Структура нагрузки (12 нед.) ===",
        "Топ МО:\n" + _fmt_volume(forecast.get("top_municipalities")),
        "Топ темы:\n" + _fmt_volume(forecast.get("top_topics")),
        "Топ группы:\n" + _fmt_volume(forecast.get("top_groups")),
        "Топ ведомства:\n" + _fmt_volume(forecast.get("top_agencies")),
        "",
        "=== Профиль тяжести и рисков ===",
        f"Распределение по классам: {_fmt_severity(forecast.get('severity_breakdown'))}.",
        "Уровни риска МО:\n" + _fmt_volume(
            [
                {"label": r.get("label"), "value": r.get("count"), "share_pct": None}
                for r in (forecast.get("risk_distribution") or [])
            ],
        ),
        "",
        "=== Тренды роста и снижения ===",
        "Рост МО:\n" + _fmt_trends(forecast.get("rising_municipalities")),
        "Рост тем:\n" + _fmt_trends(forecast.get("rising_topics")),
        "Снижение МО:\n" + _fmt_trends(forecast.get("declining_municipalities")),
        "Снижение тем:\n" + _fmt_trends(forecast.get("declining_topics")),
        f"МО с ростом/снижением: {kpis.get('rising_municipalities', 0)} / {kpis.get('declining_municipalities', 0)}.",
        "",
        "=== Карта прогноза (топ МО по тренду) ===",
        _fmt_trends(
            sorted(
                forecast.get("map_districts") or [],
                key=lambda d: float(d.get("trend_pct") or 0),
                reverse=True,
            ),
            limit=10,
        ),
        "",
        "=== Сроки обработки ===",
        f"Доступно: {processing.get('available', False)}.",
        f"Медиана закрытия: {processing.get('median_days', '—')} дн., p90: {processing.get('p90_days', '—')} дн.",
        f"Закрыто {processing.get('closed_share_pct', 0)}% ({processing.get('closed_count', 0)}), открыто {processing.get('open_count', 0)}.",
    ]

    slowest = processing.get("slowest_agencies") or []
    if slowest:
        blocks.append(
            "Медленные ведомства:\n"
            + "\n".join(
                f"- {a.get('label')}: медиана {a.get('median_days')} дн., закрыто {a.get('count')}"
                for a in slowest[:5]
            )
        )

    blocks.extend(
        [
            "",
            "=== Качество данных ===",
            f"С адресом: {quality.get('address_pct', 0)}%, геокод: {quality.get('geocode_pct', 0)}%, "
            f"дата закрытия: {quality.get('closed_at_pct', 0)}%.",
            f"Уникальных ведомств: {quality.get('agencies', '—')}, муниципалитетов в KPI: {kpis.get('municipalities', '—')}, тем: {kpis.get('topics', '—')}.",
        ]
    )

    return "\n".join(blocks)


def build_forecast_ai_summary(
    forecast: dict,
    cfg: PipelineSettings | None = None,
) -> str:
    """Генерирует управленческую сводку по всем блокам прогноза через Ollama."""
    if cfg is None:
        out = DATA_DIR / "forecast"
        cfg = PipelineSettings(
            input_path=out / "input.xlsx",
            output_dir=out,
            cache_dir=out,
            ollama_model=OLLAMA_MODEL,
        )

    context = build_forecast_context(forecast)
    horizon = forecast.get("horizon_weeks", 4)
    prompt = (
        "Составь единую аналитическую сводку для заместителя губернатора Омской области "
        f"по прогнозу проблемных обращений граждан на {horizon} недель вперёд.\n"
        "Используй ВСЕ блоки данных ниже: недельный и помесячный тренд, критичные обращения, "
        "структуру по МО/темам/ведомствам, карту рисков, рост и снижение, сроки обработки.\n\n"
        "Структура ответа (plain text, без markdown-заголовков #):\n"
        "1) Общий вывод — 2–3 предложения с главным трендом и ожидаемым объёмом.\n"
        "2) Прогноз и динамика — что ожидается по неделям и месяцам, критичные обращения.\n"
        "3) Где сосредоточена нагрузка — МО, темы, ведомства (с цифрами).\n"
        "4) Точки роста и снижения — конкретные МО и темы с трендами.\n"
        "5) Сроки и качество реагирования — если есть данные по закрытию.\n"
        "6) Рекомендации — 3–4 конкретных управленческих шага, привязанных к данным.\n\n"
        "Правила: только русский язык; без персональных данных; цифры из контекста; "
        "объём 1200–1800 символов; деловой стиль; между блоками пустая строка.\n\n"
        f"Данные прогноза:\n{context}\n"
    )
    return _chat(cfg, prompt, one_sentence=False, num_predict=700, max_chars=2000)
