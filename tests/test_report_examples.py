"""Приоритет предрасчитанных примеров в отчёте МО."""

import pandas as pd

from app.report import _build_incident_examples


def test_examples_prefer_report_over_labeled_df():
    reason = {
        "примеры_обращений": [
            {
                "text": "Прорыв трубы на улице Ленина, вода заливает подъезд целиком",
                "severity": 4,
                "label": "Критическая",
            }
        ]
    }
    huge_df = pd.DataFrame(
        {
            "муниципалитет": ["Другой м.р."] * 1000,
            "текст": ["Другая проблема с достаточно длинным текстом для фильтра"] * 1000,
            "severity": [3] * 1000,
        }
    )
    examples = _build_incident_examples(reason, "Омск г.о.", huge_df, limit=3)
    assert len(examples) == 1
    assert "Прорыв трубы" in examples[0].text
