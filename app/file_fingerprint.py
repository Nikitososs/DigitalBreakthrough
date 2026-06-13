"""Хэш содержимого загруженного файла для дедупликации."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def find_job_input_file(job_dir: Path) -> Path | None:
    if not job_dir.is_dir():
        return None
    for pattern in ("input.xlsx", "input.xls", "input.XLSX", "input.XLS"):
        candidate = job_dir / pattern
        if candidate.is_file():
            return candidate
    matches = sorted(job_dir.glob("input.*"))
    return matches[0] if matches else None
