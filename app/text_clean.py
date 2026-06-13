"""Очистка текста обращений от HTML-разметки."""

from __future__ import annotations

import html
import re

_BR_RE = re.compile(r"<br\s*/?>", re.I)
_TAG_RE = re.compile(r"<[^>]+>")


def clean_appeal_text(text: str) -> str:
    """Убирает <br>, прочие теги и лишние пробелы."""
    s = html.unescape(str(text or ""))
    s = _BR_RE.sub(" ", s)
    s = _TAG_RE.sub(" ", s)
    s = s.strip().lstrip("'\"«»")
    return " ".join(s.split())
