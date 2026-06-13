import pandas as pd

from app.text_clean import clean_appeal_text

# Список названий классов, соответствующих меткам от 0 до 4
CLASS_NAMES = [
    "Не инцидент",
    "Низкая тяжесть",
    "Средняя тяжесть",
    "Высокая тяжесть",
    "Критическая / ЧС",
]

def _clean_field(value) -> str:
    text = clean_appeal_text(str(value or ""))
    return "" if text.lower() == "nan" else text


def format_appeal_text(*, group: str = "", topic: str = "", text: str = "") -> str:
    """Единый текст обращения для ONNX (без pandas)."""
    group = _clean_field(group)
    topic = _clean_field(topic)
    text = _clean_field(text)
    parts = []
    if group:
        parts.append(f"Группа: {group}")
    if topic:
        parts.append(f"Тема: {topic}")
    if text:
        parts.append(f"Текст: {text}")
    return " | ".join(parts)


def format_input_text(row: pd.Series) -> str:
    """Преобразует строку Excel в текст для модели."""
    return format_appeal_text(
        group=row.get("Группа тем", ""),
        topic=row.get("Тема", ""),
        text=row.get("Текст инцидента", ""),
    )
