"""Сводка и рекомендации для отчётов ведомств (без LLM)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.report import SEVERITY_LABELS
from app.text_samples import clean_appeal_text, select_diverse_examples, truncate_text


@dataclass(frozen=True)
class TopicStat:
    name: str
    count: int
    percentage: float
    avg_severity: float
    critical_count: int


@dataclass(frozen=True)
class GroupStat:
    name: str
    count: int
    percentage: float


def priority_level(counts: dict[int, int]) -> str:
    c4 = counts.get(4, 0)
    c3 = counts.get(3, 0)
    total = sum(counts.get(s, 0) for s in range(1, 5))
    if c4 >= 3 or (c4 >= 1 and c3 >= 5):
        return "КРИТИЧЕСКИЙ"
    if c4 >= 1 or c3 >= 5:
        return "ВЫСОКИЙ"
    if total >= 15 or c3 >= 2:
        return "СРЕДНИЙ"
    return "НИЗКИЙ"


def top_topics_stats(df: pd.DataFrame, limit: int = 10) -> list[TopicStat]:
    if df.empty or "тема" not in df.columns:
        return []
    total = len(df) or 1
    rows: list[TopicStat] = []
    grouped = df.groupby(df["тема"].astype(str).str.strip(), dropna=False)
    for name, sub in grouped:
        topic = str(name).strip()
        if not topic or topic.lower() == "nan":
            continue
        count = len(sub)
        avg = float(sub["severity"].mean()) if "severity" in sub.columns else 0.0
        crit = int(sub["severity"].isin([3, 4]).sum()) if "severity" in sub.columns else 0
        rows.append(
            TopicStat(
                name=topic,
                count=count,
                percentage=round(100 * count / total, 1),
                avg_severity=round(avg, 2),
                critical_count=crit,
            )
        )
    rows.sort(key=lambda t: (t.critical_count, t.count, t.avg_severity), reverse=True)
    return rows[:limit]


def top_groups_stats(df: pd.DataFrame, limit: int = 8) -> list[GroupStat]:
    if df.empty or "группа" not in df.columns:
        return []
    total = len(df) or 1
    vc = df["группа"].astype(str).str.strip().value_counts()
    out: list[GroupStat] = []
    for name, count in vc.head(limit).items():
        g = str(name).strip()
        if not g or g.lower() == "nan":
            continue
        out.append(GroupStat(name=g, count=int(count), percentage=round(100 * int(count) / total, 1)))
    return out


def critical_examples(df: pd.DataFrame, *, limit: int = 5) -> list[dict]:
    if df.empty or "текст" not in df.columns:
        return []
    work = df.copy()
    if "severity" in work.columns:
        work = work[work["severity"].isin([3, 4])]
    if work.empty:
        work = df[df["severity"].isin([2, 3, 4])] if "severity" in df.columns else df
    if work.empty:
        return []

    pool: list[dict] = []
    for _, row in work.sort_values("severity", ascending=False).iterrows():
        text = clean_appeal_text(row.get("текст", ""))
        if len(text) < 40:
            continue
        sev = int(row.get("severity", 1))
        pool.append(
            {
                "text": truncate_text(text, 320),
                "severity": sev,
                "label": SEVERITY_LABELS.get(sev, str(sev)),
                "topic": str(row.get("тема", "")).strip(),
                "date": str(row.get("дата_создания", "")).strip()[:16],
            }
        )
    return select_diverse_examples(pool, limit, min_len=40, max_len=320)


def build_recommendations(
    *,
    municipality: str,
    agency: str,
    priority: str,
    counts: dict[int, int],
    topics: list[TopicStat],
    critical_total: int,
) -> list[str]:
    total = sum(counts.get(s, 0) for s in range(1, 5))
    recs: list[str] = []

    if critical_total > 0:
        recs.append(
            f"В приоритетном порядке отработать {critical_total} обращений повышенной и критической "
            f"тяжести (классы 3–4); при необходимости — с выездом на место в {municipality}."
        )
    if topics:
        top = topics[0]
        recs.append(
            f"Усилить контроль по теме «{top.name}»: {top.count} обращений "
            f"({top.percentage}% в зоне «{agency}»), из них критичных: {top.critical_count}."
        )
        if len(topics) > 1 and topics[1].critical_count > 0:
            second = topics[1]
            recs.append(
                f"Проанализировать причины по теме «{second.name}» "
                f"({second.count} обращ., критичных: {second.critical_count})."
            )
    recs.append(
        "Направить ответы заявителям по обращениям из приложения incidents.xlsx; "
        "зафиксировать сроки устранения в реестре."
    )
    if priority in ("КРИТИЧЕСКИЙ", "ВЫСОКИЙ"):
        recs.append(
            "Рекомендуется включить вопрос в повестку оперативного совещания и доложить "
            "о принятых мерах в установленный регламентный срок."
        )
    elif total >= 20:
        recs.append(
            "При системном характере обращений (20+) — рассмотреть программные меры "
            "и межведомственное взаимодействие на уровне муниципалитета."
        )
    return recs[:6]
