"""Собрать liveDemoFeed.json: обращения для demo live-потока.

Пример:
  python scripts/build_live_demo_feed.py
  python scripts/build_live_demo_feed.py --input "../proruv/data/основной файл.xlsx" --count 150
  python scripts/build_live_demo_feed.py --input "dataset_test.xlsx" --count 200
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.io import load_incidents, to_inference_frame  # noqa: E402
from pipeline.inference import run_inference  # noqa: E402
from training_utils import CLASS_NAMES, format_input_text  # noqa: E402

DATA_DIRS = [
    Path(__file__).resolve().parents[2] / "proruv" / "data",
    Path("/proruv/data"),
]
OUT = ROOT / "frontend" / "src" / "data" / "liveDemoFeed.json"

DEMO_MUNICIPALITIES = [
    "Омск г.о.",
    "Омский район",
    "Калачинский район",
    "Исилькульский район",
    "Тарский район",
    "Черлакский район",
    "Кормиловский район",
    "Марьяновский район",
    "Называевский район",
    "Тюкалинский район",
    "Большеуковский район",
    "Знаменский район",
]


def _clean_cell(value) -> str:
    text = str(value or "").strip()
    if text.startswith("'") and text.endswith("'"):
        text = text[1:-1].strip()
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1].strip()
    return text


def _is_train_workbook(path: Path) -> bool:
    try:
        cols = set(pd.read_excel(path, nrows=0).columns.astype(str))
    except Exception:
        return False
    return "Текст инцидента" in cols and "Метка_Класса" in cols


def build_feed_train(input_path: Path, count: int, seed: int) -> dict:
    print(f"Загрузка (train): {input_path}…", flush=True)
    df = pd.read_excel(input_path)
    work = df.copy()
    work["text"] = work["Текст инцидента"].map(_clean_cell)
    work = work[work["text"].str.len() >= 10]
    if work.empty:
        raise ValueError("Нет строк с текстом обращения")

    sample_n = min(count, len(work))
    rng = random.Random(seed)
    indices = rng.sample(range(len(work)), sample_n)
    sample = work.iloc[indices].reset_index(drop=True)

    items = []
    for idx, (_, row) in enumerate(sample.iterrows()):
        sev = int(row.get("Метка_Класса", 1) or 1)
        sev = max(0, min(4, sev))
        text = _clean_cell(row.get("Текст инцидента", ""))
        items.append(
            {
                "id": f"train-{idx}",
                "severity": sev,
                "label": CLASS_NAMES[sev] if sev < len(CLASS_NAMES) else CLASS_NAMES[1],
                "municipality": DEMO_MUNICIPALITIES[idx % len(DEMO_MUNICIPALITIES)],
                "group": _clean_cell(row.get("Группа тем", "")),
                "topic": _clean_cell(row.get("Тема", "")),
                "text": text[:500],
                "created_at": _clean_cell(row.get("Дата создания", "")) or None,
            }
        )

    rng.shuffle(items)
    return {
        "source_file": input_path.name,
        "count": len(items),
        "seed": seed,
        "format": "train",
        "items": items,
    }


def _largest_xlsx(directory: Path) -> Path | None:
    files = sorted(directory.glob("*.xlsx"), key=lambda p: p.stat().st_size, reverse=True)
    return files[0] if files else None


def resolve_input(path: str | None) -> Path:
    if path:
        candidate = Path(path)
        if candidate.is_dir():
            picked = _largest_xlsx(candidate)
            if picked:
                return picked
            raise FileNotFoundError(f"Нет .xlsx в {candidate}")
        if candidate.exists():
            return candidate
        raise FileNotFoundError(candidate)
    for directory in DATA_DIRS:
        if directory.exists():
            picked = _largest_xlsx(directory)
            if picked:
                return picked
    raise FileNotFoundError(f"Нет .xlsx в {DATA_DIRS}")


def build_feed(input_path: Path, count: int, seed: int, batch_size: int) -> dict:
    if _is_train_workbook(input_path):
        return build_feed_train(input_path, count, seed)

    print(f"Загрузка: {input_path} ({input_path.stat().st_size // 1024 // 1024} MB)…", flush=True)
    df = load_incidents(input_path)
    print(f"Строк: {len(df)}", flush=True)

    work = df.copy()
    work["текст"] = work["текст"].astype(str).str.strip()
    work = work[work["текст"].str.len() >= 40]
    if work.empty:
        raise ValueError("Нет строк с текстом обращения")

    sample_n = min(count, len(work))
    rng = random.Random(seed)
    indices = rng.sample(range(len(work)), sample_n)
    sample = work.iloc[indices].reset_index(drop=True)

    infer_df = to_inference_frame(sample)
    texts = infer_df.apply(format_input_text, axis=1).tolist()
    print(f"ONNX: {len(texts)} обращений…", flush=True)
    result = run_inference(texts, batch_size=batch_size)

    items = []
    for idx, (_, row) in enumerate(sample.iterrows()):
        sev = int(result.labels[idx])
        text = str(row.get("текст", "")).strip()
        items.append(
            {
                "id": str(row.get("row_id", idx)),
                "severity": sev,
                "label": result.level_names[idx] if idx < len(result.level_names) else CLASS_NAMES[sev],
                "municipality": str(row.get("муниципалитет", "")).strip(),
                "group": str(row.get("группа", "")).strip(),
                "topic": str(row.get("тема", "")).strip(),
                "text": text[:280],
                "created_at": str(row.get("дата_создания", "")).strip() or None,
            }
        )

    rng.shuffle(items)
    return {
        "source_file": input_path.name,
        "count": len(items),
        "seed": seed,
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Собрать liveDemoFeed.json для demo live-режима")
    parser.add_argument("--input", help="Путь к .xlsx (по умолчанию — крупнейший файл в proruv/data)")
    parser.add_argument("--count", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    payload = build_feed(resolve_input(args.input), args.count, args.seed, args.batch_size)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Zapisano {payload['count']} obrashchenij -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
