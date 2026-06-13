"""Фоновый прогрев геокодов по задаче (уникальные адреса → Nominatim + БД-кэш + Postgres)."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone

from app.db.geocode_cache_repo import get_geocode_many, normalize_address_key
from app.db.repository import (
    apply_geocode_to_address,
    count_geocode_stats,
    fetch_pending_address_lines,
    has_incidents_in_db,
)
from app.geocode import NOMINATIM_CONCURRENCY, geocode_address

WARMUP_BATCH = int(os.environ.get("GEOCODE_WARMUP_BATCH", "80"))
WARMUP_WORKERS = max(1, min(NOMINATIM_CONCURRENCY, WARMUP_BATCH))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class GeocodeWarmupState:
    task_id: str
    status: str = "idle"
    total_addresses: int = 0
    processed_addresses: int = 0
    geocoded_addresses: int = 0
    failed_addresses: int = 0
    geocoded_incidents: int = 0
    message: str = ""
    started_at: str = ""
    updated_at: str = ""
    stop_requested: bool = False


_lock = threading.Lock()
_states: dict[str, GeocodeWarmupState] = {}
_threads: dict[str, threading.Thread] = {}


def _clamp_pct(value: float) -> float:
    return min(100.0, max(0.0, round(value, 1)))


def _stats_payload(task_id: str, state: GeocodeWarmupState | None) -> dict:
    db_stats = count_geocode_stats(task_id) if has_incidents_in_db(task_id) else {}
    pending = int(db_stats.get("pending_addresses", 0))
    total = int(db_stats.get("total_addresses", 0))
    geocoded_incidents = int(db_stats.get("geocoded_incidents", 0))
    st = state or GeocodeWarmupState(task_id=task_id)
    progress = _clamp_pct((total - pending) / total * 100) if total else 100.0
    if pending == 0 and st.status in {"running", "idle"}:
        status = "done" if total else st.status
    else:
        status = st.status
    return {
        "task_id": task_id,
        "status": status,
        "total_addresses": total,
        "pending_addresses": pending,
        "processed_addresses": st.processed_addresses,
        "geocoded_addresses": st.geocoded_addresses,
        "failed_addresses": st.failed_addresses,
        "geocoded_incidents": geocoded_incidents,
        "progress_pct": 100.0 if status == "done" else progress,
        "message": st.message,
        "started_at": st.started_at,
        "updated_at": st.updated_at,
    }


def get_warmup_status(task_id: str) -> dict:
    with _lock:
        state = _states.get(task_id)
    return _stats_payload(task_id, state)


def start_warmup(task_id: str) -> dict:
    with _lock:
        state = _states.get(task_id)
        if state and state.status == "running":
            return _stats_payload(task_id, state)
        if state and state.status == "done":
            db_stats = count_geocode_stats(task_id)
            if int(db_stats.get("pending_addresses", 0)) == 0:
                return _stats_payload(task_id, state)

        state = GeocodeWarmupState(
            task_id=task_id,
            status="running",
            started_at=_now_iso(),
            updated_at=_now_iso(),
        )
        _states[task_id] = state
        thread = threading.Thread(
            target=_run_warmup,
            args=(task_id,),
            name=f"geocode-warmup-{task_id}",
            daemon=True,
        )
        _threads[task_id] = thread
        thread.start()
    return _stats_payload(task_id, state)


def stop_warmup(task_id: str) -> dict:
    with _lock:
        state = _states.get(task_id)
        if state:
            state.stop_requested = True
            state.message = "Остановка…"
            state.updated_at = _now_iso()
    return get_warmup_status(task_id)


def _resolve_batch(addresses: list[str]) -> list[tuple[str, tuple[float, float] | None]]:
    """Кэш → пропуск failed → параллельный Nominatim для новых адресов."""
    cache = get_geocode_many(addresses)
    results: list[tuple[str, tuple[float, float] | None]] = []
    to_fetch: list[str] = []

    for address_line in addresses:
        key = normalize_address_key(address_line)
        hit = cache.get(key)
        if hit and not hit.get("failed") and hit.get("lat") is not None:
            results.append((address_line, (float(hit["lat"]), float(hit["lng"]))))
        elif hit and hit.get("failed"):
            results.append((address_line, None))
        else:
            to_fetch.append(address_line)

    if not to_fetch:
        return results

    workers = min(WARMUP_WORKERS, len(to_fetch))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(geocode_address, addr, cache_only=False): addr for addr in to_fetch}
        for future in as_completed(futures):
            address_line = futures[future]
            try:
                coords = future.result()
            except Exception:
                coords = None
            results.append((address_line, coords))

    return results


def _run_warmup(task_id: str) -> None:
    try:
        while True:
            with _lock:
                state = _states[task_id]
                if state.stop_requested:
                    state.status = "stopped"
                    state.message = "Остановлено пользователем"
                    state.updated_at = _now_iso()
                    return

            addresses = fetch_pending_address_lines(task_id, limit=WARMUP_BATCH)
            if not addresses:
                with _lock:
                    state = _states[task_id]
                    state.status = "done"
                    state.message = "Все адреса обработаны"
                    state.updated_at = _now_iso()
                return

            with _lock:
                state = _states[task_id]
                if state.total_addresses == 0:
                    stats = count_geocode_stats(task_id)
                    state.total_addresses = int(stats.get("total_addresses", 0))

            batch_results = _resolve_batch(addresses)

            for address_line, coords in batch_results:
                with _lock:
                    state = _states[task_id]
                    if state.stop_requested:
                        state.status = "stopped"
                        state.message = "Остановлено пользователем"
                        state.updated_at = _now_iso()
                        return

                with _lock:
                    state = _states[task_id]
                    state.processed_addresses += 1
                    state.updated_at = _now_iso()

                if coords:
                    updated_rows = apply_geocode_to_address(task_id, address_line, coords[0], coords[1])
                    with _lock:
                        state = _states[task_id]
                        state.geocoded_addresses += 1
                        state.geocoded_incidents += updated_rows
                        state.message = f"Геокодировано адресов: {state.geocoded_addresses}"
                else:
                    with _lock:
                        state = _states[task_id]
                        state.failed_addresses += 1

    except Exception as exc:
        with _lock:
            state = _states.get(task_id)
            if state:
                state.status = "error"
                state.message = str(exc)
                state.updated_at = _now_iso()


def schedule_warmup_after_import(task_id: str) -> None:
    if not has_incidents_in_db(task_id):
        return
    stats = count_geocode_stats(task_id)
    if int(stats.get("pending_addresses", 0)) <= 0:
        return
    start_warmup(task_id)
