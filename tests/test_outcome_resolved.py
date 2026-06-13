"""Критерий решённости по колонке «Итог»."""

import pandas as pd

from app.resolved import is_resolved_outcome, is_resolved_row


def test_is_resolved_outcome_values():
    assert is_resolved_outcome("Решено")
    assert is_resolved_outcome("разъяснено")
    assert is_resolved_outcome("Перенаправлено в другое ведомство")
    assert not is_resolved_outcome("Отклонено")
    assert not is_resolved_outcome("")
    assert not is_resolved_outcome(None)


def test_is_resolved_row_from_parquet():
    row = pd.Series({"итог": "Решено", "severity": 3})
    assert is_resolved_row(row)
    row2 = pd.Series({"итог": "В работе", "manually_resolved": True})
    assert is_resolved_row(row2)
