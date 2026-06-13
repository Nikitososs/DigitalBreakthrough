"""Сборка адреса из колонок выгрузки (X, Y, Z, W)."""

from __future__ import annotations


def _clean(value) -> str:
    text = str(value or "").strip()
    if text.lower() in {"", "nan", "none", "<na>"}:
        return ""
    return text


def has_street_address(row: dict) -> bool:
    return bool(_clean(row.get("улица") or row.get("street")))


def format_address_line(
    *,
    municipality: str = "",
    settlement: str = "",
    street: str = "",
    house: str = "",
) -> tuple[str, bool]:
    """Возвращает (строка адреса, есть_ли_улица)."""
    municipality = _clean(municipality)
    settlement = _clean(settlement)
    street = _clean(street)
    house = _clean(house)

    if not street:
        fallback = settlement or municipality or "Омская область"
        return fallback, False

    parts: list[str] = []
    if street:
        low = street.lower()
        if not low.startswith(("ул", "пр", "пер", "бул", "пл", "шос", "наб")):
            street = f"ул. {street}"
        parts.append(street)
    if house:
        parts.append(f"д. {house}")
    locality = settlement or municipality
    if locality:
        parts.append(locality)
    parts.append("Омская область, Россия")
    return ", ".join(parts), True


def geocode_query_from_row(row: dict) -> tuple[str, bool]:
    return format_address_line(
        municipality=_clean(row.get("муниципалитет")),
        settlement=_clean(row.get("населенный_пункт")),
        street=_clean(row.get("улица")),
        house=_clean(row.get("дом")),
    )
