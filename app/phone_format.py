"""Форматирование российских телефонных номеров для отображения."""

from __future__ import annotations

import re

_EXT_RE = re.compile(r"\s*(?:доб\.?|ext\.?|#)\s*(\S+)", re.IGNORECASE)
_SPLIT_RE = re.compile(r"[,;]+")
_JUNK_TAIL_RE = re.compile(r"[\s\-–—(]+$")
_PAREN_RE = re.compile(
    r"^\s*(?:\+7|8)?\s*\(\s*([\d\s\-]+)\s*\)\s*(.+)$",
    re.IGNORECASE,
)


def _clean_display(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    return _JUNK_TAIL_RE.sub("", cleaned).strip()


def _extract_digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _normalize_digits(digits: str) -> str | None:
    if not digits:
        return None
    if len(digits) == 11 and digits[0] in "78":
        return "7" + digits[1:]
    if len(digits) == 10:
        if digits[0] == "9" or digits.startswith("381"):
            return "7" + digits
    return None


def _format_local_digits(digits: str) -> str:
    if len(digits) == 6:
        return f"{digits[0:2]}-{digits[2:4]}-{digits[4:6]}"
    if len(digits) == 7:
        return f"{digits[0:3]}-{digits[3:5]}-{digits[5:7]}"
    if len(digits) == 5:
        if digits[0] == "2":
            if digits[1] == "2":
                if digits[2] >= "6":
                    return f"{digits[0]}-{digits[1:3]}-{digits[3:5]}"
                return f"{digits[0:2]}-{digits[2:5]}"
            if digits[1] == "1" and digits[2] == "2" and digits[3] >= "8":
                return f"{digits[0:2]}-{digits[2:5]}"
            return f"{digits[0]}-{digits[1:3]}-{digits[3:5]}"
        if digits[0] == "3":
            return f"{digits[0]}-{digits[1:3]}-{digits[3:5]}"
        return f"{digits[0:2]}-{digits[2:5]}"
    if len(digits) == 4:
        return f"{digits[0:2]}-{digits[2:4]}"
    return digits


def _normalize_local_display(local: str) -> str:
    local = _JUNK_TAIL_RE.sub("", local.strip())
    if not local:
        return ""

    digits = _extract_digits(local)
    if re.search(r"[\s\-–—]", local):
        parts = [p for p in re.split(r"[\s\-–—]+", local) if p]
        if len(parts) == 3:
            return f"{parts[0]}-{parts[1]}-{parts[2]}"
        if len(parts) == 2:
            first, second = parts
            if len(digits) == 5 and len(first) == 2 and len(second) == 3:
                if (
                    second[0] in "23"
                    or first == "22"
                    or (first[0] == "2" and first[1] == "7")
                ):
                    return f"{first}-{second}"
                return _format_local_digits(digits)
            return f"{first}-{second}"

    return _format_local_digits(digits) if digits else local


def _format_from_parens(area_raw: str, local_raw: str) -> str:
    area = _extract_digits(area_raw)
    local = _normalize_local_display(local_raw)
    if not area or not local:
        return ""
    return f"+7 ({area}) {local}"


def _format_landline(rest: str) -> str | None:
    if rest.startswith("3812") and len(rest) >= 10:
        area = "3812"
        local = rest[4:10]
        return f"+7 ({area}) {_format_local_digits(local)}"
    if rest.startswith("381") and len(rest) >= 10:
        area = rest[:5]
        local = rest[5:10]
        return f"+7 ({area}) {_format_local_digits(local)}"
    if len(rest) == 10:
        area = rest[:3]
        local = rest[3:]
        return f"+7 ({area}) {_format_local_digits(local)}"
    return None


def _format_digits11(digits11: str) -> str | None:
    if len(digits11) != 11 or digits11[0] != "7":
        return None
    if digits11[1] == "9":
        return (
            f"+7 ({digits11[1:4]}) {digits11[4:7]}-"
            f"{digits11[7:9]}-{digits11[9:11]}"
        )
    return _format_landline(digits11[1:])


def _format_single_part(part: str) -> str:
    raw = _clean_display(part)
    if not raw:
        return ""

    ext_match = _EXT_RE.search(raw)
    extension = f" доб. {ext_match.group(1)}" if ext_match else ""
    main = _EXT_RE.split(raw, maxsplit=1)[0].strip()
    main = _JUNK_TAIL_RE.sub("", main).strip()

    paren_match = _PAREN_RE.match(main)
    if paren_match:
        formatted = _format_from_parens(paren_match.group(1), paren_match.group(2))
        if formatted:
            return formatted + extension

    digits = _extract_digits(main)
    normalized = _normalize_digits(digits)
    if normalized:
        formatted = _format_digits11(normalized)
        if formatted:
            return formatted + extension

    return _clean_display(part)


def format_phone_ru(phone: str | None) -> str | None:
    """Нормализует российский телефон к виду +7 (XXX) XXX-XX-XX."""
    if phone is None:
        return None
    text = str(phone).strip()
    if not text:
        return None

    parts = [p.strip() for p in _SPLIT_RE.split(text) if p.strip()]
    if not parts:
        parts = [text]

    formatted_parts = [_format_single_part(part) for part in parts]
    formatted_parts = [p for p in formatted_parts if p]
    if formatted_parts:
        return ", ".join(formatted_parts)

    return _clean_display(text)
