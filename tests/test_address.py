"""Адрес из колонок X/Y/Z выгрузки."""

from app.address import format_address_line, has_street_address


def test_format_address_with_street_and_house():
    line, precise = format_address_line(
        municipality="Омск г.о.",
        settlement="г. Омск",
        street="Волочаевская",
        house="13",
    )
    assert precise is True
    assert "Волочаевская" in line
    assert "д. 13" in line
    assert "Омск" in line


def test_format_address_municipality_only():
    line, precise = format_address_line(municipality="Тарский район")
    assert precise is False
    assert line == "Тарский район"


def test_has_street_address():
    assert has_street_address({"улица": "Ленина"}) is True
    assert has_street_address({"улица": ""}) is False
