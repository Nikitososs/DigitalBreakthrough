from app.text_clean import clean_appeal_text


def test_strips_br_tags():
    assert clean_appeal_text("Первая часть<br>—<br>Вторая часть") == "Первая часть — Вторая часть"


def test_strips_html_entities_and_tags():
    assert clean_appeal_text("Текст&lt;br&gt;продолжение") == "Текст продолжение"
    assert clean_appeal_text("<p>Жалоба</p> на <b>отопление</b>") == "Жалоба на отопление"
