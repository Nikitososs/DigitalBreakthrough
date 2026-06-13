"""Фикстуры для тестов cabinet_export (proruv/data)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

DESKTOP = Path(os.environ.get("USERPROFILE", "")) / "OneDrive" / "Рабочий стол"
DEFAULT_DATA_DIR = DESKTOP / "proruv" / "data"
DEFAULT_DATASET_DIR = DESKTOP / "Hackaton_Backend" / "dataset"

DEFAULT_TEST_XLSX = DEFAULT_DATA_DIR / "тестовый файл.xlsx"
DEFAULT_MAIN_XLSX = DEFAULT_DATA_DIR / "основной файл.xlsx"


def _resolve_xlsx(candidates: list[Path | None]) -> Path | None:
    for path in candidates:
        if path is not None and path.is_file():
            return path
    return None


@pytest.fixture(scope="session")
def test_xlsx_path() -> Path:
    env_path = os.environ.get("TEST_XLSX")
    path = _resolve_xlsx(
        [
            Path(env_path) if env_path else None,
            DEFAULT_TEST_XLSX,
            DEFAULT_DATASET_DIR / "тестовый файл.xlsx",
        ]
    )
    if path is None:
        pytest.skip(
            f"Нет тестового xlsx. Положите файл в {DEFAULT_DATA_DIR} "
            f"или задайте TEST_XLSX."
        )
    return path


@pytest.fixture(scope="session")
def main_xlsx_path() -> Path:
    env_path = os.environ.get("MAIN_XLSX")
    path = _resolve_xlsx(
        [
            Path(env_path) if env_path else None,
            DEFAULT_MAIN_XLSX,
            DEFAULT_DATASET_DIR / "основной файл.xlsx",
        ]
    )
    if path is None:
        pytest.skip(f"Нет основного xlsx в {DEFAULT_DATA_DIR}")
    return path
