"""Формирование Excel-отчётов и JSON для API / фронтенда."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.llm_text import is_complete_summary, normalize_llm_summary
from app.report_dates import _parse_report_date
from app.resolved import filter_unresolved, is_resolved_row, outcome_column
from app.text_samples import clean_appeal_text, sample_problem_texts, select_diverse_examples
from schemas import (
    CriticalDistrictCard,
    DashboardResponse,
    DistrictReport,
    DistrictReportResponse,
    DistrictShortInfo,
    IncidentExample,
    SeverityStat,
    ThematicGroupStat,
    ThemeCount,
)

SEVERITY_LABELS: dict[int, str] = {
    0: "Не инцидент",
    1: "Низкая",
    2: "Средняя",
    3: "Высокая",
    4: "Критическая",
}


def severity_label(value) -> str:
    """Текстовая метка тяжести по числу. Пустая строка на нечисловой вход."""
    try:
        sev = int(value)
    except (TypeError, ValueError):
        return ""
    return SEVERITY_LABELS.get(sev, str(sev))


def _dashboard_meta(report: dict) -> dict:
    stats = report.get("stats") or {}
    start = _parse_report_date(stats.get("start_date"))
    end = _parse_report_date(stats.get("end_date"))
    total = stats.get("rows_processed")
    if total is None:
        total = sum(_safe_int(r.get("total_incidents", 0)) for r in report.get("all", []))
    problems = stats.get("problem_count")
    return {
        "start_date": start,
        "end_date": end,
        "total_incidents": _safe_int(total) if total else None,
        "problem_count": _safe_int(problems) if problems is not None else None,
    }


def _first_example_text(reason: dict) -> str:
    raw = reason.get("примеры_обращений")
    if not isinstance(raw, list) or not raw:
        return ""
    item = raw[0]
    if isinstance(item, dict):
        return clean_appeal_text(str(item.get("text", "")))[:300]
    return clean_appeal_text(str(item))[:300]


def _build_incident_examples(
    reason: dict,
    muni: str,
    labeled_df: pd.DataFrame | None = None,
    *,
    limit: int = 6,
) -> list[IncidentExample]:
    raw = reason.get("примеры_обращений")
    raw_candidates: list[dict] = []
    if isinstance(raw, list) and raw:
        for item in raw:
            if isinstance(item, dict):
                sev = _safe_int(item.get("severity", 0))
                text = clean_appeal_text(item.get("text", ""))
            else:
                sev = 1
                text = clean_appeal_text(item)
            if sev <= 0 or len(text) < 40:
                continue
            raw_candidates.append(
                {
                    "text": text,
                    "severity": sev,
                    "label": str(
                        item.get("label", SEVERITY_LABELS.get(sev, ""))
                        if isinstance(item, dict)
                        else SEVERITY_LABELS.get(sev, "")
                    ),
                }
            )

    if raw_candidates:
        diverse = select_diverse_examples(raw_candidates, limit)
        return [
            IncidentExample(
                text=s["text"],
                severity=_safe_int(s["severity"]),
                label=str(s.get("label", SEVERITY_LABELS.get(_safe_int(s["severity"]), ""))),
            )
            for s in diverse
        ]

    if labeled_df is not None and not labeled_df.empty and "текст" in labeled_df.columns:
        problems = _unresolved_problems_for_muni(labeled_df, muni)
        samples = sample_problem_texts(problems, muni, n=limit)
        if samples:
            return [
                IncidentExample(
                    text=s["text"],
                    severity=_safe_int(s["severity"]),
                    label=str(s.get("label", SEVERITY_LABELS.get(_safe_int(s["severity"]), ""))),
                )
                for s in samples
            ]

    return []


def _unresolved_problems_df(labeled_df: pd.DataFrame) -> pd.DataFrame:
    if labeled_df.empty:
        return labeled_df
    unresolved = filter_unresolved(labeled_df)
    if "severity" in unresolved.columns:
        return unresolved.loc[unresolved["severity"].fillna(0).astype(float) > 0]
    if "is_problem" in unresolved.columns:
        return unresolved.loc[unresolved["is_problem"].fillna(False).astype(bool)]
    return unresolved


def build_severity_breakdown(labeled_df: pd.DataFrame) -> list[dict]:
    """Счётчики по классам 1–4 (нерешённые проблемные) для каждого муниципалитета."""
    problems = _unresolved_problems_df(labeled_df)
    if problems.empty or "severity" not in problems.columns:
        return []
    rows: list[dict] = []
    for muni, sub in problems.groupby("муниципалитет"):
        for sev in range(1, 5):
            count = int((sub["severity"] == sev).sum())
            if count <= 0:
                continue
            rows.append(
                {
                    "муниципалитет": str(muni),
                    "severity": sev,
                    "label": SEVERITY_LABELS[sev],
                    "count": count,
                }
            )
    return rows


def build_unresolved_topics_groups(labeled_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Темы и группы по нерешённым проблемным обращениям (для Excel-экспорта)."""
    from app.breakdown import _agg_by_dimension

    problems = _unresolved_problems_df(labeled_df)
    topics = _agg_by_dimension(problems, "тема", "тема")
    groups = _agg_by_dimension(problems, "группа", "группа")
    return topics, groups


def build_resolved_stats(labeled_df: pd.DataFrame) -> list[dict]:
    """Доля решённых проблемных обращений по муниципалитетам."""
    if labeled_df.empty or "муниципалитет" not in labeled_df.columns:
        return []
    outcome_col = outcome_column(labeled_df)
    if outcome_col is None and "manually_resolved" not in labeled_df.columns:
        return []

    sev_col = "severity" if "severity" in labeled_df.columns else "Метка_Класса"
    rows: list[dict] = []
    for muni, sub in labeled_df.groupby("муниципалитет"):
        if sev_col in sub.columns:
            problems = sub.loc[sub[sev_col].fillna(0).astype(int) > 0]
        elif "is_problem" in sub.columns:
            problems = sub.loc[sub["is_problem"].fillna(False).astype(bool)]
        else:
            problems = sub
        problem_n = int(len(problems))
        if problem_n == 0:
            continue
        resolved_n = int(sum(is_resolved_row(r) for _, r in problems.iterrows()))
        rows.append(
            {
                "муниципалитет": str(muni),
                "problem_count": problem_n,
                "resolved_count": resolved_n,
                "resolved_pct": round(100.0 * resolved_n / problem_n, 1),
            }
        )
    return rows


def _resolved_for_municipality(
    report: dict,
    muni: str,
    labeled_df: pd.DataFrame | None = None,
) -> tuple[float | None, int | None, int | None]:
    if labeled_df is not None and not labeled_df.empty and outcome_column(labeled_df):
        stats = build_resolved_stats(labeled_df)
        for row in stats:
            if row["муниципалитет"] == muni:
                return row["resolved_pct"], row["resolved_count"], row["problem_count"]
    for row in report.get("resolved_stats") or []:
        if str(row.get("муниципалитет", "")) == muni:
            return (
                float(row["resolved_pct"]) if row.get("resolved_pct") is not None else None,
                _safe_int(row.get("resolved_count")) if row.get("resolved_count") is not None else None,
                _safe_int(row.get("problem_count")) if row.get("problem_count") is not None else None,
            )
    if labeled_df is not None and not labeled_df.empty:
        stats = build_resolved_stats(labeled_df)
        for row in stats:
            if row["муниципалитет"] == muni:
                return row["resolved_pct"], row["resolved_count"], row["problem_count"]
    return None, None, None


def _safe_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        if isinstance(value, float) and np.isnan(value):
            return default
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "<na>"}:
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    return int(round(_safe_float(value, default)))


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    out = df.copy()
    for col in out.select_dtypes(include="object").columns:
        out[col] = out[col].fillna("")
    records = out.to_dict(orient="records")
    for row in records:
        for key, val in row.items():
            if isinstance(val, float) and np.isnan(val):
                row[key] = None
    return records


def write_report_json(
    output_dir: Path,
    top_all: pd.DataFrame,
    top10: pd.DataFrame,
    top3: pd.DataFrame,
    topics_df: pd.DataFrame,
    groups_df: pd.DataFrame,
    reasons_df: pd.DataFrame,
    summary_text: str,
    stats: dict,
    severity_breakdown: list[dict] | None = None,
    resolved_stats: list[dict] | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary_text": summary_text,
        "top3": _df_to_records(top3),
        "top10": _df_to_records(top10),
        "all": _df_to_records(top_all),
        "topics": _df_to_records(topics_df),
        "groups": _df_to_records(groups_df),
        "reasons": _df_to_records(reasons_df),
        "severity_breakdown": severity_breakdown or [],
        "resolved_stats": resolved_stats or [],
        "stats": stats,
    }
    path = output_dir / "report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _main_problem(row: pd.Series) -> str:
    for key in ("топ_тема", "ключевые_темы", "топ_группа"):
        val = str(row.get(key, "")).strip()
        if val:
            return val.split(";")[0].split("(")[0].strip()
    return "Не определено"


def _criticality_status(score: int, severity_mean: float) -> str:
    if score >= 85 or severity_mean >= 3.5:
        return "КРИТИЧНЫЙ"
    if score >= 70 or severity_mean >= 2.8:
        return "ОЧЕНЬ ВЫСОКИЙ"
    if score >= 55:
        return "ВЫСОКИЙ"
    return "ПОВЫШЕННЫЙ"


def _parse_theme_counts(key_topics: str, limit: int = 5) -> list[ThemeCount]:
    items = []
    for part in str(key_topics).split(";"):
        part = part.strip()
        if not part:
            continue
        if "(" in part and ")" in part:
            name, cnt = part.rsplit("(", 1)
            try:
                count = int(cnt.replace(")", "").strip())
            except ValueError:
                count = 0
            items.append(ThemeCount(theme=name.strip(), count=count))
        else:
            items.append(ThemeCount(theme=part, count=0))
        if len(items) >= limit:
            break
    return items


def _district_summary(row: dict, reason: dict) -> str | None:
    paragraph = str(row.get("summary_paragraph") or "").strip()
    if paragraph and is_complete_summary(paragraph, min_len=20):
        return paragraph
    one_line = str(row.get("summary_text") or reason.get("summary_text") or "").strip()
    if one_line and is_complete_summary(one_line, min_len=15):
        return one_line
    if paragraph:
        return paragraph
    return one_line or None


def _unresolved_problems_for_muni(labeled_df: pd.DataFrame, muni: str) -> pd.DataFrame:
    sub = labeled_df[labeled_df["муниципалитет"].astype(str) == str(muni)]
    return _unresolved_problems_df(sub)


def _district_summary_unresolved_fallback(
    muni: str,
    target: dict,
    reason: dict,
    labeled_df: pd.DataFrame | None,
) -> str | None:
    if labeled_df is None or labeled_df.empty:
        return None
    problems = _unresolved_problems_for_muni(labeled_df, muni)
    score = _safe_int(target.get("score", 50))
    top_theme = str(reason.get("топ_тема", "") or _main_problem({**target, **reason}))
    total = _safe_int(target.get("total_incidents", 0))
    if problems.empty:
        return f"В муниципалитете «{muni}» нерешённых проблемных обращений не выявлено."
    critical = int((problems["severity"] >= 4).sum()) if "severity" in problems.columns else 0
    text = (
        f"«{muni}»: {len(problems)} нерешённых проблемных обращений из {total}, "
        f"индекс проблемности {score} из 100"
    )
    if critical:
        text += f", критических: {critical}"
    text += f". Основная тема — {top_theme}."
    return text


def _build_themes_stat(
    muni: str,
    topics: list[dict],
    total_incidents: int,
    labeled_df: pd.DataFrame | None,
    *,
    problem_count: int | None = None,
) -> list[ThematicGroupStat]:
    theme_col = "тема"
    if (
        labeled_df is not None
        and not labeled_df.empty
        and theme_col in labeled_df.columns
        and "муниципалитет" in labeled_df.columns
    ):
        sub = labeled_df[labeled_df["муниципалитет"].astype(str) == str(muni)]
        if "severity" in sub.columns:
            problems = sub.loc[sub["severity"].fillna(0).astype(float) > 0]
        elif "is_problem" in sub.columns:
            problems = sub.loc[sub["is_problem"].fillna(False).astype(bool)]
        else:
            problems = sub
        if problems.empty:
            return []

        problem_n = int(len(problems))
        rows: list[ThematicGroupStat] = []
        for theme, group in problems.groupby(theme_col):
            theme_name = str(theme).strip()
            if not theme_name:
                continue
            total_in_theme = int(len(group))
            unresolved_n = int(len(filter_unresolved(group)))
            resolved_n = total_in_theme - unresolved_n
            resolved_pct = round(100.0 * resolved_n / total_in_theme, 1) if total_in_theme else 0.0
            pct = round(total_in_theme / problem_n * 100, 1) if problem_n else 0.0
            rows.append(
                ThematicGroupStat(
                    group_name=theme_name,
                    count=unresolved_n,
                    percentage=pct,
                    total_count=total_in_theme,
                    resolved_pct=resolved_pct,
                )
            )
        rows.sort(key=lambda x: x.count, reverse=True)
        return rows

    themes_stat: list[ThematicGroupStat] = []
    denom = problem_count or total_incidents
    for t in sorted(topics, key=lambda x: x.get("count", 0), reverse=True):
        count = _safe_int(t.get("count", 0))
        pct = round(count / denom * 100, 1) if denom else 0.0
        themes_stat.append(
            ThematicGroupStat(
                group_name=str(t.get("тема", "")),
                count=count,
                percentage=pct,
                total_count=count,
            )
        )
    return themes_stat


def _build_severity_stat(
    muni: str,
    severity_rows: list[dict],
    total_incidents: int,
    labeled_df: pd.DataFrame | None,
) -> list[SeverityStat]:
    if labeled_df is not None and not labeled_df.empty:
        problems = _unresolved_problems_for_muni(labeled_df, muni)
        if problems.empty or "severity" not in problems.columns:
            return []
        unresolved_n = int(len(problems))
        stat: list[SeverityStat] = []
        for sev in range(1, 5):
            count = int((problems["severity"] == sev).sum())
            if count <= 0:
                continue
            pct = round(count / unresolved_n * 100, 1) if unresolved_n else 0.0
            stat.append(
                SeverityStat(
                    severity=sev,
                    label=SEVERITY_LABELS.get(sev, str(sev)),
                    count=count,
                    percentage=pct,
                )
            )
        return stat

    return []


def build_dashboard(report: dict) -> DashboardResponse:
    top10 = report.get("top10", [])
    reasons = {r["муниципалитет"]: r for r in report.get("reasons", [])}

    map_data: list[DistrictShortInfo] = []
    for row in report.get("all", []):
        muni = row["муниципалитет"]
        reason = reasons.get(muni, {})
        map_data.append(
            DistrictShortInfo(
                district_id=_safe_int(row.get("district_id", row.get("rank", 0))),
                district_name=muni,
                score=_safe_int(row.get("score", 50)),
                main_problem=_main_problem({**row, **reason}),
            )
        )

    top_districts = []
    for row in top10:
        muni = row["муниципалитет"]
        reason = reasons.get(muni, {})
        top_districts.append(
            DistrictShortInfo(
                district_id=_safe_int(row.get("district_id", row.get("rank", 0))),
                district_name=muni,
                score=_safe_int(row.get("score", 50)),
                main_problem=_main_problem({**row, **reason}),
                analytical_summary=_district_summary(row, reason),
            )
        )

    critical_districts = []
    for row in report.get("top3", []):
        muni = row["муниципалитет"]
        reason = reasons.get(muni, {})
        merged = {**row, **reason}
        sample = _first_example_text(reason)
        critical_districts.append(
            CriticalDistrictCard(
                district_id=_safe_int(row.get("district_id", row.get("rank", 0))),
                district_name=muni,
                criticality_status=_criticality_status(
                    _safe_int(row.get("score", 50)),
                    _safe_float(row.get("severity_mean", 0)),
                ),
                score=_safe_int(row.get("score", 50)),
                top_themes=_parse_theme_counts(merged.get("ключевые_темы", "")),
                sample_incident_text=sample[:300],
                analytical_summary=_district_summary(row, reason),
                total_incidents=_safe_int(row.get("total_incidents", row.get("problem_count", 0))),
            )
        )

    meta = _dashboard_meta(report)
    return DashboardResponse(
        map_data=map_data,
        top_districts=top_districts,
        critical_districts=critical_districts,
        start_date=meta["start_date"],
        end_date=meta["end_date"],
        total_incidents=meta["total_incidents"],
        problem_count=meta["problem_count"],
    )


def build_district_report(
    report: dict,
    district_id: int,
    *,
    analytical_summary: str | None = None,
    labeled_df: pd.DataFrame | None = None,
) -> DistrictReportResponse | None:
    all_rows = report.get("all", [])
    target = next(
        (r for r in all_rows if int(r.get("district_id", r.get("rank", -1))) == district_id),
        None,
    )
    if target is None:
        return None

    muni = target["муниципалитет"]
    reason = next((r for r in report.get("reasons", []) if r["муниципалитет"] == muni), {})
    topics = [t for t in report.get("topics", []) if t.get("муниципалитет") == muni]
    total = _safe_int(target.get("total_incidents", 0))
    problem_count_hint = _safe_int(target.get("problem_count", 0)) or None
    themes_stat = _build_themes_stat(
        muni,
        topics,
        total,
        labeled_df,
        problem_count=problem_count_hint,
    )

    examples = _build_incident_examples(reason, muni, labeled_df)

    severity_rows = [
        r for r in report.get("severity_breakdown", []) if str(r.get("муниципалитет", "")) == muni
    ]
    severity_stat = _build_severity_stat(muni, severity_rows, total, labeled_df)

    summary = analytical_summary or _district_summary_unresolved_fallback(muni, target, reason, labeled_df)
    if not summary:
        unresolved_n = len(_unresolved_problems_for_muni(labeled_df, muni)) if labeled_df is not None and not labeled_df.empty else None
        count_phrase = (
            f"{unresolved_n} нерешённых проблемных обращений"
            if unresolved_n is not None
            else f"{_safe_int(target.get('problem_count', 0))} проблемных обращений"
        )
        summary = (
            f"Муниципалитет «{muni}»: {count_phrase} "
            f"из {total}, индекс проблемности {_safe_int(target.get('score', 50))} из 100. "
            f"Главная тема — {reason.get('топ_тема', '') or _main_problem({**target, **reason})}."
        )
    if not is_complete_summary(summary, min_len=30):
        summary = _district_summary_unresolved_fallback(muni, target, reason, labeled_df) or summary
    summary = normalize_llm_summary(summary, one_sentence=False, max_chars=800)

    period = _dashboard_meta(report)
    resolved_pct, resolved_count, problem_count = _resolved_for_municipality(report, muni, labeled_df)
    return DistrictReportResponse(
        data=DistrictReport(
            district_id=district_id,
            district_name=muni,
            score=_safe_int(target.get("score", 50)),
            analytical_summary=summary,
            total_incidents=total,
            top_category=str(reason.get("топ_тема", "") or _main_problem({**target, **reason})),
            categories_count=len(themes_stat),
            resolved_pct=resolved_pct,
            resolved_count=resolved_count,
            problem_count=problem_count or _safe_int(target.get("problem_count", 0)) or None,
            start_date=period["start_date"],
            end_date=period["end_date"],
            themes_stat=themes_stat,
            severity_stat=severity_stat,
            incident_examples=examples,
        )
    )


def load_report_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
