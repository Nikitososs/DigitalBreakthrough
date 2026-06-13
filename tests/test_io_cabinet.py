"""Тесты загрузки cabinet_export (тестовый / основной файл)."""

from app.io import load_incidents


def test_cabinet_export_test_file(test_xlsx_path):
    df = load_incidents(test_xlsx_path)
    assert df.attrs.get("column_layout") == "official_export"
    assert len(df) == 26_201
    assert set(df.columns) >= {
        "id_обращения",
        "номер_инцидента",
        "дата_создания",
        "дата_закрытия",
        "шаг_инцидента",
        "итог",
        "группа",
        "тема",
        "муниципалитет",
        "населенный_пункт",
        "улица",
        "дом",
        "текст",
        "row_id",
    }
    assert df["row_id"].astype(str).str.match(r"^\d+$").all()
    dedup = df.attrs.get("dedup") or {}
    assert dedup.get("removed", 0) == 0
    assert not any("время" in str(c).lower() for c in df.columns)


def test_cabinet_export_main_smoke(main_xlsx_path):
    df = load_incidents(main_xlsx_path)
    assert df.attrs.get("column_layout") == "official_export"
    assert len(df) > 400_000
    assert df["муниципалитет"].astype(str).str.len().gt(0).any()
    assert df["текст"].astype(str).str.len().gt(10).any()
