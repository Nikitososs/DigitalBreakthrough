"""Проверка промптов, шаблонов и нормализации аналитической сводки."""

from __future__ import annotations

import pandas as pd

from app.llm_text import normalize_llm_summary
from app.summary import _SYSTEM_PROMPT, _leadership_prompt
from app.summary_templates import (
    template_municipality_paragraph,
    template_top3_paragraph,
)


def _sample_rank_row(**overrides) -> pd.Series:
    base = {
        "муниципалитет": "Омский г.о.",
        "rank": 1,
        "score": 92,
        "problem_count": 340,
        "total_incidents": 1200,
        "problem_share": 0.28,
        "critical_count": 5,
        "severity_mean": 2.7,
    }
    base.update(overrides)
    return pd.Series(base)


def _sample_reason_row(**overrides) -> pd.Series:
    base = {
        "топ_тема": "Отопление",
        "топ_группа": "ЖКХ",
        "ключевые_темы": "Отопление (120); Водоснабжение (45); Дороги (30)",
        "ключевые_группы": "ЖКХ (180); Дороги (40)",
    }
    base.update(overrides)
    return pd.Series(base)


def test_system_prompt_score_semantics():
    assert "чем выше" in _SYSTEM_PROMPT
    assert "100" in _SYSTEM_PROMPT
    assert "health score" not in _SYSTEM_PROMPT.lower()


def test_leadership_prompt_score_semantics():
    prompt = _leadership_prompt(_sample_rank_row(), _sample_reason_row(), extended=False)
    assert "чем выше — тем хуже" in prompt
    assert "чем ниже" not in prompt
    assert "health score" not in prompt.lower()
    assert "Ситуация:" in prompt
    assert "Ключевые темы:" in prompt
    assert "Рекомендация:" in prompt
    assert "400–500" in prompt


def test_leadership_prompt_extended_has_criticality():
    prompt = _leadership_prompt(_sample_rank_row(), _sample_reason_row(), extended=True)
    assert "Критичность:" in prompt
    assert "600–800" in prompt
    assert "Отопление (120)" in prompt or "«Отопление» (120)" in prompt


def test_leadership_prompt_limits_themes_in_data():
    prompt = _leadership_prompt(_sample_rank_row(), _sample_reason_row(), extended=False)
    assert "Дороги (30)" not in prompt


def test_template_municipality_paragraph_structure_and_semantics():
    text = template_municipality_paragraph(_sample_rank_row(), _sample_reason_row())
    assert text.startswith("Ситуация:")
    assert "Ключевые темы:" in text
    assert "Рекомендация:" in text
    assert "чем выше — тем хуже" in text
    assert "health score" not in text.lower()
    assert "Водоснабжение" in text and "(45)" in text
    assert "Дороги (30)" not in text
    assert len(text) <= 550


def test_template_top3_high_score_is_critical():
    text = template_top3_paragraph(_sample_rank_row(score=92), _sample_reason_row())
    assert "Критичность: критический" in text
    assert "чем выше — тем хуже" in text
    assert len(text) <= 850


def test_template_top3_moderate_score():
    text = template_top3_paragraph(
        _sample_rank_row(score=60, critical_count=0),
        _sample_reason_row(),
    )
    assert "Критичность: повышенное внимание" in text


def test_normalize_llm_summary_preserves_paragraph_breaks():
    raw = (
        "Ситуация: Омский г.о. — 1-е место, индекс 92 из 100.\n\n"
        "Ключевые темы: «Отопление» (120).\n\n"
        "Рекомендация: Провести проверку котельных."
    )
    out = normalize_llm_summary(raw, one_sentence=False, max_chars=800)
    assert "\n\n" in out
    assert out.startswith("Ситуация:")
    assert "Ключевые темы:" in out
    assert "Рекомендация:" in out


def test_normalize_llm_summary_truncates_paragraphs():
    long_block = "Ситуация: " + "слово " * 200
    raw = f"{long_block}\n\nКлючевые темы: «ЖКХ» (10).\n\nРекомендация: Действовать."
    out = normalize_llm_summary(raw, one_sentence=False, max_chars=120)
    assert len(out) <= 125
    assert out.startswith("Ситуация:")
