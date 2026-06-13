"""Сборка пакетов обращений по ведомствам (оператор)."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

DEFAULT_AGENCY = "Иные ведомства Омской области"


def _normalize_key(text: str) -> str:
    raw = unicodedata.normalize("NFKC", str(text or "")).lower()
    raw = re.sub(r"[^\w\s]", " ", raw, flags=re.UNICODE)
    return re.sub(r"\s+", " ", raw).strip()


def topics_similar(a: str, b: str) -> bool:
    na = _normalize_key(a)
    nb = _normalize_key(b)
    if not na or not nb:
        return na == nb
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    wa = na.split(" ")[0] if na else ""
    wb = nb.split(" ")[0] if nb else ""
    return len(wa) >= 4 and wa == wb


def _merge_topic_labels(topics: list[str]) -> list[str]:
    out: list[str] = []
    for topic in topics:
        t = str(topic or "").strip()
        if not t:
            continue
        if any(topics_similar(u, t) for u in out):
            continue
        out.append(t)
    return sorted(out, key=lambda s: s.casefold())


def _severity_counts(items: list[dict]) -> dict[int, int]:
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for item in items:
        sev = int(item.get("severity") or 0)
        if sev in counts:
            counts[sev] += 1
    return counts


def _make_bundle(agency_name: str, group: str, items: list[dict], topics: list[str]) -> dict:
    merged_topics = _merge_topic_labels(topics)
    group_label = group or "Без категории"
    if merged_topics:
        head = ", ".join(merged_topics[:4])
        suffix = "…" if len(merged_topics) > 4 else ""
        label = f"{group_label} · {head}{suffix}"
    else:
        label = group_label
    topic_key = "|".join(merged_topics) or "_"
    return {
        "id": f"{agency_name}::{group_label}::{topic_key}",
        "group": group_label,
        "topics": merged_topics,
        "label": label,
        "items": items,
        "count": len(items),
        "severity_counts": _severity_counts(items),
    }


def build_agency_packages(items: list[dict]) -> list[dict]:
    """Пакеты: ведомство → категория (группа) → обращения."""
    agency_map: dict[str, dict] = {}

    for item in items:
        agency_name = str(item.get("agency") or "").strip() or DEFAULT_AGENCY
        if agency_name not in agency_map:
            agency_map[agency_name] = {
                "agency_name": agency_name,
                "agency": agency_name,
                "agency_email": item.get("agency_email"),
                "by_group": defaultdict(list),
            }
        group = str(item.get("group") or item.get("category") or "Без категории").strip() or "Без категории"
        agency_map[agency_name]["by_group"][group].append(item)

    packages: list[dict] = []
    for agency_name, bucket in agency_map.items():
        bundles: list[dict] = []
        for group, group_items in bucket["by_group"].items():
            topics = [str(i.get("topic") or "").strip() for i in group_items if i.get("topic")]
            topic_clusters: list[list[str]] = []
            for topic in topics:
                placed = False
                for cluster in topic_clusters:
                    if any(topics_similar(t, topic) for t in cluster):
                        cluster.append(topic)
                        placed = True
                        break
                if not placed:
                    topic_clusters.append([topic])

            if len(topic_clusters) <= 1:
                bundles.append(_make_bundle(agency_name, group, group_items, topics))
                continue

            assigned: set[str] = set()
            for cluster in topic_clusters:
                cluster_items = []
                for item in group_items:
                    item_id = str(item.get("id") or "")
                    if item_id in assigned:
                        continue
                    item_topic = str(item.get("topic") or "").strip()
                    if not item_topic:
                        continue
                    if any(topics_similar(t, item_topic) for t in cluster):
                        cluster_items.append(item)
                        assigned.add(item_id)
                if cluster_items:
                    bundles.append(_make_bundle(agency_name, group, cluster_items, cluster))

            rest = [i for i in group_items if str(i.get("id") or "") not in assigned]
            if rest:
                bundles.append(
                    _make_bundle(
                        agency_name,
                        group,
                        rest,
                        [str(i.get("topic") or "") for i in rest],
                    )
                )

        bundles.sort(key=lambda b: b["count"], reverse=True)
        total = sum(b["count"] for b in bundles)
        packages.append(
            {
                "agency_name": agency_name,
                "agency": bucket["agency"],
                "agency_email": bucket.get("agency_email"),
                "bundles": bundles,
                "total": total,
            }
        )

    packages.sort(key=lambda p: p["total"], reverse=True)
    return packages


def _merge_severity_counts(a: dict, b: dict) -> dict:
    out = {1: 0, 2: 0, 3: 0, 4: 0}
    for src in (a, b):
        for key, val in (src or {}).items():
            sev = int(key)
            if sev in out:
                out[sev] += int(val or 0)
    return out


def merge_agency_packages(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Объединяет пакеты с нескольких страниц (по id bundle, dedupe items)."""
    by_agency: dict[str, dict] = {}

    for pkg in [*existing, *incoming]:
        agency_name = str(pkg.get("agency_name") or pkg.get("agency") or "").strip()
        if not agency_name:
            continue
        if agency_name not in by_agency:
            by_agency[agency_name] = {
                "agency_name": agency_name,
                "agency": pkg.get("agency") or agency_name,
                "agency_email": pkg.get("agency_email"),
                "bundles": {},
            }
        bucket = by_agency[agency_name]
        if not bucket.get("agency_email") and pkg.get("agency_email"):
            bucket["agency_email"] = pkg.get("agency_email")

        for bundle in pkg.get("bundles") or []:
            bundle_id = str(bundle.get("id") or "")
            if bundle_id not in bucket["bundles"]:
                bucket["bundles"][bundle_id] = {
                    **bundle,
                    "items": list(bundle.get("items") or []),
                }
                continue
            prev = bucket["bundles"][bundle_id]
            seen = {str(i.get("id") or "") for i in prev.get("items") or []}
            for item in bundle.get("items") or []:
                item_id = str(item.get("id") or "")
                if item_id and item_id in seen:
                    continue
                prev["items"].append(item)
                if item_id:
                    seen.add(item_id)
            prev["count"] = len(prev["items"])
            prev["severity_counts"] = _merge_severity_counts(
                prev.get("severity_counts"),
                bundle.get("severity_counts"),
            )

    packages: list[dict] = []
    for agency_name, bucket in by_agency.items():
        bundles = list(bucket["bundles"].values())
        bundles.sort(key=lambda b: b.get("count", 0), reverse=True)
        packages.append(
            {
                "agency_name": agency_name,
                "agency": bucket["agency"],
                "agency_email": bucket.get("agency_email"),
                "bundles": bundles,
                "total": sum(int(b.get("count") or 0) for b in bundles),
            }
        )
    packages.sort(key=lambda p: p["total"], reverse=True)
    return packages
