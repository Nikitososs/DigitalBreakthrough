"""Сопоставление «Группа тем» → ведомство и муниципалитет → администрация МО."""



from __future__ import annotations



import json

import re

from functools import lru_cache

from pathlib import Path

from app.phone_format import format_phone_ru


MAPPING_PATH = Path(__file__).resolve().parents[1] / "data" / "agency_mapping.json"

MUNICIPALITY_PATH = Path(__file__).resolve().parents[1] / "data" / "municipality_agencies.json"

_UNSAFE_PATH = re.compile(r'[<>:"/\\|?*\x00-\x1f]')





@lru_cache(maxsize=1)

def load_agency_mapping() -> dict:

    with MAPPING_PATH.open(encoding="utf-8") as fh:

        return json.load(fh)





@lru_cache(maxsize=1)

def load_municipality_mapping() -> dict:

    with MUNICIPALITY_PATH.open(encoding="utf-8") as fh:

        return json.load(fh)





def _normalize_municipality_key(name: str) -> str:

    key = str(name or "").strip()

    if not key:

        return ""

    aliases = load_municipality_mapping().get("municipality_aliases") or {}

    return str(aliases.get(key, key)).strip()





def resolve_agency(group: str) -> str:

    """Возвращает полное название ведомства для группы тем."""

    mapping = load_agency_mapping()

    key = str(group or "").strip()

    if not key:

        return mapping.get("fallback_agency", "Иные ведомства")

    return mapping.get("group_to_agency", {}).get(key, mapping.get("fallback_agency", key))





def region_name() -> str:

    return str(load_agency_mapping().get("region", "Омская область"))





def resolve_agency_email(agency: str) -> str | None:

    """Контакт ведомства для сопроводительного письма (если задан в mapping)."""

    mapping = load_agency_mapping()

    emails = mapping.get("agency_emails") or {}

    key = str(agency or "").strip()

    if not key:

        return None

    return emails.get(key) or emails.get(mapping.get("fallback_agency", ""))





def resolve_municipality_admin(municipality: str) -> dict:

    """Контакт администрации МО (с нормализацией имён из Excel/кэша)."""

    mapping = load_municipality_mapping()

    municipalities = mapping.get("municipalities") or {}

    key = _normalize_municipality_key(municipality)

    entry = municipalities.get(key)

    if not entry:

        return {

            "municipality": key or str(municipality or "").strip(),

            "administration": None,

            "email": None,

            "phone": None,

            "website": None,

            "contact_verified": False,

        }

    return {

        "municipality": key,

        "administration": entry.get("administration"),

        "email": entry.get("email") or None,

        "phone": format_phone_ru(entry.get("phone")),

        "website": entry.get("website") or None,

        "contact_verified": bool(entry.get("contact_verified")),

        "source_url": entry.get("source_url") or None,

    }





def resolve_contact(municipality: str, agency: str) -> dict:

    """Региональное ведомство (по группе) + местная администрация (по МО)."""

    agency_name = str(agency or "").strip()

    return {

        "agency": agency_name,

        "agency_email": resolve_agency_email(agency_name),

        "municipality_admin": resolve_municipality_admin(municipality),

    }





def safe_path_segment(name: str, *, max_len: int = 80) -> str:

    """Безопасное имя папки/файла в ZIP."""

    cleaned = _UNSAFE_PATH.sub("_", str(name or "").strip())

    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")

    if not cleaned:

        cleaned = "unnamed"

    if len(cleaned) > max_len:

        cleaned = cleaned[: max_len - 1].rstrip() + "…"

    return cleaned


