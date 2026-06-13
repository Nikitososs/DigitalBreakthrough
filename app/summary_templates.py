"""Шаблонные справки по структурированным данным — быстро и с цифрами."""

from __future__ import annotations

import pandas as pd


def _safe_int(val, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _first_theme(key_topics: str) -> str:
    part = str(key_topics or "").split(";")[0].strip()
    if "(" in part:
        part = part.rsplit("(", 1)[0].strip()
    return part


def _top_themes_limited(key_topics: str, limit: int = 2) -> list[tuple[str, int]]:
    items: list[tuple[str, int]] = []
    for part in str(key_topics or "").split(";"):
        part = part.strip()
        if not part:
            continue
        if "(" in part and ")" in part:
            name, cnt = part.rsplit("(", 1)
            try:
                count = int(cnt.replace(")", "").strip())
            except ValueError:
                count = 0
            items.append((name.strip(), count))
        else:
            items.append((part, 0))
        if len(items) >= limit:
            break
    return items


def _format_themes_line(key_topics: str, *, limit: int = 2) -> str:
    themes = _top_themes_limited(key_topics, limit=limit)
    if not themes:
        return ""
    return "; ".join(f"«{name}» ({count})" if count else f"«{name}»" for name, count in themes)


def _as_series(row: pd.Series | pd.DataFrame | None, fallback: pd.Series) -> pd.Series:
    if row is None:
        return fallback
    if isinstance(row, pd.DataFrame):
        return row.iloc[0]
    return row


def template_district_sentence(rank_row: pd.Series, reason_row: pd.Series | None = None) -> str:
    """Одно предложение для карточки / reasons — с цифрами и топ-темой."""
    reason_row = _as_series(reason_row, rank_row)
    muni = str(rank_row.get("муниципалитет", ""))
    problems = _safe_int(rank_row.get("problem_count"))
    total = _safe_int(rank_row.get("total_incidents"))
    share = _safe_float(rank_row.get("problem_share"))
    critical = _safe_int(rank_row.get("critical_count"))
    score = _safe_int(rank_row.get("score", rank_row.get("health_score")))
    top_theme = str(reason_row.get("топ_тема") or _first_theme(reason_row.get("ключевые_темы", "")))
    top_group = str(reason_row.get("топ_группа", "")).strip()

    crit = f", критических — {critical}" if critical else ""
    theme = f"главная тема «{top_theme}»" if top_theme else "тематика разнородная"
    group = f", группа «{top_group}»" if top_group else ""
    return (
        f"«{muni}»: индекс проблемности {score} из 100, {problems} проблемных "
        f"из {total} ({share:.0%}){crit}; {theme}{group}."
    )


def template_municipality_paragraph(rank_row: pd.Series, reason_row: pd.Series | None = None) -> str:
    """Краткая сводка для карточки / municipality_summaries.xlsx."""
    reason_row = _as_series(reason_row, rank_row)
    muni = str(rank_row.get("муниципалитет", ""))
    rank = _safe_int(rank_row.get("rank"))
    score = _safe_int(rank_row.get("score", rank_row.get("health_score")))
    problems = _safe_int(rank_row.get("problem_count"))
    total = _safe_int(rank_row.get("total_incidents"))
    share = _safe_float(rank_row.get("problem_share"))
    critical = _safe_int(rank_row.get("critical_count"))
    sev = _safe_float(rank_row.get("severity_mean"))
    top_group = str(reason_row.get("топ_группа", "")).strip()
    key_themes = str(reason_row.get("ключевые_темы", "")).strip()
    themes_line = _format_themes_line(key_themes, limit=2)

    crit = f", критических (класс 4) — {critical}" if critical else ""
    situation = (
        f"Ситуация: «{muni}» — {rank}-е место в рейтинге, индекс проблемности {score} из 100 "
        f"(чем выше — тем хуже). {problems} проблемных из {total} обращений ({share:.0%}), "
        f"средняя тяжесть {sev:.1f}{crit}."
    )
    themes_parts = []
    if themes_line:
        themes_parts.append(themes_line)
    elif str(reason_row.get("топ_тема") or ""):
        themes_parts.append(f"«{reason_row.get('топ_тема')}»")
    if top_group:
        themes_parts.append(f"группа «{top_group}»")
    themes = f"Ключевые темы: {'; '.join(themes_parts)}." if themes_parts else ""
    top_theme = str(reason_row.get("топ_тема") or _first_theme(key_themes))
    rec_target = top_theme or top_group or "основным темам жалоб"
    recommendation = (
        f"Рекомендация: сфокусировать контроль и ресурсы на «{rec_target}» "
        f"с еженедельным отчётом в областной штаб."
    )
    return "\n\n".join(x for x in (situation, themes, recommendation) if x)


def template_top3_paragraph(rank_row: pd.Series, reason_row: pd.Series | None = None) -> str:
    """Развёрнутая сводка для критических Top-3 (drilldown / отчётность)."""
    reason_row = _as_series(reason_row, rank_row)
    muni = str(rank_row.get("муниципалитет", ""))
    rank = _safe_int(rank_row.get("rank"))
    score = _safe_int(rank_row.get("score", rank_row.get("health_score")))
    problems = _safe_int(rank_row.get("problem_count"))
    total = _safe_int(rank_row.get("total_incidents"))
    share = _safe_float(rank_row.get("problem_share"))
    critical = _safe_int(rank_row.get("critical_count"))
    sev = _safe_float(rank_row.get("severity_mean"))
    top_theme = str(reason_row.get("топ_тема") or _first_theme(reason_row.get("ключевые_темы", "")))
    top_group = str(reason_row.get("топ_группа", "")).strip()
    key_themes = str(reason_row.get("ключевые_темы", "")).strip()
    key_groups = str(reason_row.get("ключевые_группы", "")).strip()
    themes_line = _format_themes_line(key_themes, limit=2)

    crit = f", критических (класс 4) — {critical}" if critical else ""
    situation = (
        f"Ситуация: «{muni}» — {rank}-е место, индекс проблемности {score} из 100 "
        f"(чем выше — тем хуже). {problems} проблемных из {total} ({share:.0%}), "
        f"средняя тяжесть {sev:.1f}{crit}."
    )
    themes_parts = []
    if themes_line:
        themes_parts.append(themes_line)
    elif top_theme:
        themes_parts.append(f"«{top_theme}»")
    if top_group:
        themes_parts.append(f"группа «{top_group}»")
    themes = f"Ключевые темы: {'; '.join(themes_parts)}." if themes_parts else ""

    if score >= 85 or critical >= 3:
        risk = "Критичность: критический уровень — требуется оперативное реагирование."
    elif score >= 70:
        risk = "Критичность: очень высокий уровень проблемности."
    else:
        risk = "Критичность: повышенное внимание руководства."

    group_hint = ""
    if key_groups:
        group_hint = f" (группа «{key_groups.split(';')[0].split('(')[0].strip()}»)"
    rec_target = top_theme or top_group or "основным темам жалоб"
    recommendation = (
        f"Рекомендация: в течение 3 рабочих дней развернуть межведомственную проверку "
        f"по «{rec_target}»{group_hint} и доложить исполнение в областной штаб."
    )
    return "\n\n".join(x for x in (situation, themes, risk, recommendation) if x)


def enrich_reasons_with_templates(
    reasons_df: pd.DataFrame,
    rankings_df: pd.DataFrame,
) -> pd.DataFrame:
    """summary_text по шаблону для каждого МО из Top-N."""
    if reasons_df.empty:
        return reasons_df
    rank_by_muni = rankings_df.set_index("муниципалитет") if not rankings_df.empty else pd.DataFrame()
    out = reasons_df.copy()
    texts: list[str] = []
    for _, row in out.iterrows():
        muni = row["муниципалитет"]
        rank_row = rank_by_muni.loc[muni] if muni in rank_by_muni.index else row
        texts.append(template_district_sentence(rank_row, row))
    out["summary_text"] = texts
    return out


def build_municipality_summaries_from_templates(
    top_df: pd.DataFrame,
    reasons_df: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    reason_by_muni = reasons_df.set_index("муниципалитет") if not reasons_df.empty else pd.DataFrame()
    for _, row in top_df.iterrows():
        muni = row["муниципалитет"]
        reason = reason_by_muni.loc[muni] if muni in reason_by_muni.index else None
        rows.append(
            {
                "district_id": int(row["district_id"]),
                "муниципалитет": muni,
                "rank": int(row["rank"]),
                "problem_count": int(row["problem_count"]),
                "summary": template_municipality_paragraph(row, reason),
            }
        )
    return pd.DataFrame(rows)


def build_top3_summaries_from_templates(
    top3_df: pd.DataFrame,
    reasons_df: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    reason_by_muni = reasons_df.set_index("муниципалитет") if not reasons_df.empty else pd.DataFrame()
    for _, row in top3_df.iterrows():
        muni = row["муниципалитет"]
        reason = reason_by_muni.loc[muni] if muni in reason_by_muni.index else None
        rows.append(
            {
                "district_id": int(row["district_id"]),
                "муниципалитет": muni,
                "rank": int(row["rank"]),
                "problem_count": int(row["problem_count"]),
                "summary": template_top3_paragraph(row, reason),
            }
        )
    return pd.DataFrame(rows)
