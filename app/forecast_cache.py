"""Кэш прогноза: повторные запросы не пересчитывают 500k+ строк."""

from __future__ import annotations

import time
from threading import Lock

import pandas as pd

from app.config.llm import OLLAMA_MODEL
from app.db.repository import load_forecast_dataframe
from app.forecast import build_forecast
from app.forecast_summary import build_forecast_ai_summary

_lock = Lock()
_data_cache: tuple[float, pd.DataFrame, int] | None = None
_forecast_cache: dict[int, tuple[float, dict]] = {}
_ai_summary_cache: dict[int, tuple[float, dict]] = {}

DATA_TTL_SEC = 300
FORECAST_TTL_SEC = 120


def get_forecast_response(horizon_weeks: int) -> dict:
    now = time.time()
    with _lock:
        global _data_cache
        if _data_cache is None or now - _data_cache[0] > DATA_TTL_SEC:
            df, jobs_count, last_upload = load_forecast_dataframe()
            _data_cache = (now, df, jobs_count, last_upload)
            _forecast_cache.clear()
        else:
            df, jobs_count, last_upload = _data_cache[1], _data_cache[2], _data_cache[3]

        cached = _forecast_cache.get(horizon_weeks)
        if cached and now - cached[0] < FORECAST_TTL_SEC:
            return cached[1]

    result = build_forecast(
        df,
        horizon_weeks=horizon_weeks,
        incident_count=len(df),
        jobs_count=jobs_count,
        last_upload=last_upload or None,
    )

    with _lock:
        _forecast_cache[horizon_weeks] = (now, result)
    return result


def invalidate_forecast_cache() -> None:
    """Сброс кэша после новой загрузки данных (опционально)."""
    global _data_cache
    with _lock:
        _data_cache = None
        _forecast_cache.clear()
        _ai_summary_cache.clear()


def get_forecast_ai_summary(horizon_weeks: int, *, force: bool = False) -> dict:
    """LLM-сводка по прогнозу; кэш 10 мин, сбрасывается вместе с прогнозом."""
    now = time.time()
    ai_ttl = 600

    with _lock:
        if not force:
            cached = _ai_summary_cache.get(horizon_weeks)
            if cached and now - cached[0] < ai_ttl:
                return {**cached[1], "from_cache": True}

    forecast = get_forecast_response(horizon_weeks)
    summary = build_forecast_ai_summary(forecast)
    payload = {
        "summary": summary,
        "horizon_weeks": horizon_weeks,
        "model": OLLAMA_MODEL,
        "from_cache": False,
    }

    with _lock:
        _ai_summary_cache[horizon_weeks] = (now, payload)
    return payload
