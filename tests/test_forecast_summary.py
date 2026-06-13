"""Тесты контекста и AI-сводки прогноза."""

from unittest.mock import patch

import pandas as pd

from app.forecast import build_forecast
from app.forecast_summary import build_forecast_ai_summary, build_forecast_context


def _sample_df(n: int = 120) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="7D")
    rows = []
    for i, dt in enumerate(dates):
        rows.append(
            {
                "дата_создания": dt.strftime("%Y-%m-%d"),
                "is_problem": True,
                "severity": 2 + (i % 3),
                "муниципалитет": "г. Омск" if i % 2 == 0 else "Омский р-н",
                "тема": "ЖКХ" if i % 3 else "Дороги",
                "группа": "ЖКХ",
                "ведомство": "УК",
                "has_address": True,
                "closed_at": dt.strftime("%Y-%m-%d") if i % 4 == 0 else None,
            }
        )
    return pd.DataFrame(rows)


def test_build_forecast_context_includes_all_sections():
    df = _sample_df()
    forecast = build_forecast(df, horizon_weeks=4, incident_count=len(df), jobs_count=1)
    context = build_forecast_context(forecast)

    assert "Горизонт прогноза: 4 нед." in context
    assert "=== Регион (недельный тренд) ===" in context
    assert "=== Критичные обращения" in context
    assert "=== Помесячная динамика" in context
    assert "=== Структура нагрузки" in context
    assert "=== Тренды роста и снижения ===" in context
    assert "=== Сроки обработки ===" in context


@patch("app.forecast_summary._chat", return_value="Тестовая AI-сводка по прогнозу.")
def test_build_forecast_ai_summary_calls_llm(mock_chat):
    df = _sample_df()
    forecast = build_forecast(df, horizon_weeks=4)
    text = build_forecast_ai_summary(forecast)

    assert text == "Тестовая AI-сводка по прогнозу."
    mock_chat.assert_called_once()
    prompt = mock_chat.call_args[0][1]
    assert "Горизонт прогноза: 4 нед." in prompt
    assert "Рекомендации" in prompt
