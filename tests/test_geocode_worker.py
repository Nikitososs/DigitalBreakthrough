"""Тесты прогресса фонового геокодирования."""

from __future__ import annotations

from unittest.mock import patch

from app.geocode_worker import GeocodeWarmupState, _stats_payload


def test_progress_uses_db_and_never_exceeds_100():
    state = GeocodeWarmupState(
        task_id="task-1",
        status="running",
        total_addresses=100,
        processed_addresses=150,
        geocoded_addresses=80,
        failed_addresses=70,
    )
    with patch("app.geocode_worker.has_incidents_in_db", return_value=True), patch(
        "app.geocode_worker.count_geocode_stats",
        return_value={
            "total_addresses": 100,
            "pending_addresses": 20,
            "geocoded_incidents": 500,
        },
    ):
        payload = _stats_payload("task-1", state)

    assert payload["progress_pct"] == 80.0
    assert payload["progress_pct"] <= 100.0


def test_progress_done_is_100():
    state = GeocodeWarmupState(task_id="task-1", status="running")
    with patch("app.geocode_worker.has_incidents_in_db", return_value=True), patch(
        "app.geocode_worker.count_geocode_stats",
        return_value={
            "total_addresses": 50,
            "pending_addresses": 0,
            "geocoded_incidents": 200,
        },
    ):
        payload = _stats_payload("task-1", state)

    assert payload["status"] == "done"
    assert payload["progress_pct"] == 100.0
