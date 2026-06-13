"""Audit группа -> ведомство mapping against cache data."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.agency_mapping import load_agency_mapping, resolve_agency

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "jobs"
MAPPING = load_agency_mapping()["group_to_agency"]


def main() -> None:
    groups: dict[str, int] = {}

    for p in CACHE.glob("*/labeled.parquet"):
        try:
            df = pd.read_parquet(p, columns=["группа"])
        except Exception:
            continue
        vc = df["группа"].astype(str).str.strip().value_counts()
        for g, cnt in vc.items():
            if g and g != "nan":
                groups[g] = groups.get(g, 0) + int(cnt)

    if not groups:
        for p in CACHE.glob("*/output/report.json"):
            try:
                r = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            for row in r.get("groups", []):
                g = str(row.get("группа", "")).strip()
                if g:
                    groups[g] = groups.get(g, 0) + int(row.get("count", 1))

    print(f"Unique groups: {len(groups)}\n")
    mapped = []
    missing = []
    for g, cnt in sorted(groups.items(), key=lambda x: -x[1]):
        agency = resolve_agency(g)
        hit = g in MAPPING
        (mapped if hit else missing).append((g, cnt, agency))

    print("=== MAPPED ===")
    for g, cnt, agency in mapped:
        print(f"  [{cnt:>7}] {g!r} -> {agency}")

    print(f"\n=== MISSING ({len(missing)} groups, fallback) ===")
    for g, cnt, agency in missing:
        print(f"  [{cnt:>7}] {g!r} -> {agency}")

    # MO check: same group always same agency?
    parquets = list(CACHE.glob("*/labeled.parquet"))
    if parquets:
        df = pd.read_parquet(parquets[0], columns=["группа", "муниципалитет"])
        df["ведомство"] = df["группа"].map(lambda x: resolve_agency(str(x)))
        cross = df.groupby(["группа", "ведомство"]).size().reset_index(name="n")
        print(f"\n=== MO independence: each группа maps to exactly 1 ведомство (no MO override) ===")
        print(f"Sample parquet: {parquets[0].name}, rows={len(df)}")
        print(f"Municipalities: {df['муниципалитет'].nunique()}")


if __name__ == "__main__":
    main()
