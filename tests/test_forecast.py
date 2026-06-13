"""Тесты прогноза обращений."""

import pandas as pd

from app.forecast import build_forecast, _weekly_counts, _prepare_problem_df


def _synthetic_weekly_df(weeks: int = 8, base: int = 10, slope: int = 2) -> pd.DataFrame:
    rows = []
    start = pd.Timestamp("2024-01-01")
    for w in range(weeks):
        week_start = start + pd.Timedelta(weeks=w)
        count = base + slope * w
        for _ in range(count):
            rows.append(
                {
                    "дата_создания": week_start + pd.Timedelta(days=2),
                    "муниципалитет": "г. Омск",
                    "тема": "ЖКХ",
                    "is_problem": True,
                }
            )
        rows.append(
            {
                "дата_создания": week_start + pd.Timedelta(days=3),
                "муниципалитет": "Омский район",
                "тема": "Дороги",
                "is_problem": True,
            }
        )
    return pd.DataFrame(rows)


def test_build_forecast_region_series():
    df = _synthetic_weekly_df(weeks=8)
    result = build_forecast(df, horizon_weeks=4, incident_count=len(df), jobs_count=2)

    assert result["source"] == "database"
    assert result["incident_count"] > 0
    assert result["horizon_weeks"] == 4
    assert result["region_series"]["label"] == "Регион"
    history = [p for p in result["region_series"]["points"] if not p["is_forecast"]]
    forecast = [p for p in result["region_series"]["points"] if p["is_forecast"]]
    assert len(history) == 8
    assert len(forecast) == 4
    assert result["region_series"]["trend_pct"] > 0
    assert result["summary_text"]
    assert "kpis" in result
    assert "region_chart" in result
    assert "monthly_series" in result
    assert result["kpis"]["history_weeks"] == 8


def test_rising_detection():
    rows = []
    start = pd.Timestamp("2024-01-01")
    for w in range(6):
        week = start + pd.Timedelta(weeks=w)
        for _ in range(5 + w * 3):
            rows.append(
                {
                    "дата_создания": week,
                    "муниципалитет": "Растущий МО",
                    "тема": "ЖКХ",
                    "is_problem": True,
                }
            )
        rows.append(
            {
                "дата_создания": week,
                "муниципалитет": "Стабильный МО",
                "тема": "Стабильная тема",
                "is_problem": True,
            }
        )
    df = pd.DataFrame(rows)
    result = build_forecast(df, horizon_weeks=4)

    rising_muni = result["rising_municipalities"]
    labels = [s["label"] for s in rising_muni]
    assert "Растущий МО" in labels
    assert "Стабильный МО" not in labels


def test_empty_data_handling():
    empty = pd.DataFrame()
    result = build_forecast(empty, horizon_weeks=4)

    assert result["region_series"]["points"] == []
    assert result["rising_municipalities"] == []
    assert result["rising_topics"] == []
    assert "архиве" in result["summary_text"]


def test_low_confidence_short_history():
    df = _synthetic_weekly_df(weeks=2)
    result = build_forecast(df, horizon_weeks=2)

    assert result["region_series"]["confidence"] == "low"
    assert result["region_series"]["risk_level"] == "низкая уверенность"
    forecast = [p for p in result["region_series"]["points"] if p["is_forecast"]]
    assert len(forecast) == 2
    assert all(p["predicted"] is not None for p in forecast)


def test_prepare_problem_df_filters():
    df = pd.DataFrame(
        {
            "дата_создания": ["2024-01-15", "2024-01-16"],
            "is_problem": [True, False],
        }
    )
    prepared = _prepare_problem_df(df)
    assert len(prepared) == 1


def test_build_forecast_includes_resolved_rows():
    """Прогноз учитывает все проблемные обращения, не только открытые."""
    rows = []
    start = pd.Timestamp("2024-01-01")
    for w in range(6):
        week = start + pd.Timedelta(weeks=w)
        rows.append(
            {
                "дата_создания": week,
                "муниципалитет": "г. Омск",
                "тема": "ЖКХ",
                "is_problem": True,
                "итог": "решено",
            }
        )
        rows.append(
            {
                "дата_создания": week,
                "муниципалитет": "г. Омск",
                "тема": "ЖКХ",
                "is_problem": True,
            }
        )
    df = pd.DataFrame(rows)
    result = build_forecast(df, horizon_weeks=4)
    assert result["incident_count"] == len(df)
    history = [p for p in result["region_series"]["points"] if not p["is_forecast"]]
    assert sum(p["actual"] for p in history) == len(df)


def test_critical_series_severity_filter():
    rows = []
    start = pd.Timestamp("2024-01-01")
    for w in range(6):
        week = start + pd.Timedelta(weeks=w)
        rows.append({"дата_создания": week, "severity": 2, "is_problem": True, "муниципалитет": "A"})
        for _ in range(2 + w):
            rows.append({"дата_создания": week, "severity": 4, "is_problem": True, "муниципалитет": "A"})
    df = pd.DataFrame(rows)
    result = build_forecast(df, horizon_weeks=4)
    history = [p for p in result["critical_chart"]["points"] if not p["is_forecast"]]
    region_history = [p for p in result["region_chart"]["points"] if not p["is_forecast"]]
    assert result["critical_chart"]["label"] == "Критичные (3–4)"
    assert sum(p["actual"] for p in history) < sum(p["actual"] for p in region_history)


def test_data_quality_and_processing():
    df = _synthetic_weekly_df(weeks=6)
    df["has_address"] = True
    df["is_geocoded"] = False
    df["ведомство"] = "МинЖКХ"
    df.loc[df.index[:10], "closed_at"] = (pd.to_datetime(df.loc[df.index[:10], "дата_создания"]) + pd.Timedelta(days=5)).astype(str)
    result = build_forecast(df, horizon_weeks=4, jobs_count=3, last_upload="2024-06-01T12:00:00")
    dq = result["data_quality"]
    assert dq["address_pct"] == 100.0
    assert dq["geocode_pct"] == 0.0
    assert dq["agencies"] >= 1
    assert dq["jobs_count"] == 3
    assert result["top_agencies"]
    proc = result["processing"]
    assert proc["closed_count"] >= 5
    assert proc["available"] is True
    assert proc["median_days"] is not None


def test_weekly_counts_by_municipality():
    df = _prepare_problem_df(_synthetic_weekly_df(weeks=4))
    weekly = _weekly_counts(df, "муниципалитет")
    assert "week" in weekly.columns
    assert "label" in weekly.columns
    assert weekly["label"].nunique() >= 2


def test_map_districts_for_forecast():
    df = _synthetic_weekly_df(weeks=8)
    result = build_forecast(df, horizon_weeks=4)
    districts = result["map_districts"]
    assert isinstance(districts, list)
    assert len(districts) >= 1
    omsk = next((d for d in districts if "Омск" in d["name"]), districts[0])
    assert "score" in omsk
    assert "trend_pct" in omsk
    assert "forecast_next_week" in omsk
    assert 0 <= omsk["score"] <= 100
