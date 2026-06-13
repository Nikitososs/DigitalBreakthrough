from app.incident_packages import build_agency_packages, merge_agency_packages, topics_similar


def test_topics_similar_merges_prefix():
    assert topics_similar("отопление", "отопление в домах")
    assert not topics_similar("вода", "дороги")


def test_build_agency_packages_groups_by_agency():
    items = [
        {"id": "1", "severity": 4, "group": "ЖКХ", "topic": "отопление", "agency": "МинЖКХ"},
        {"id": "2", "severity": 3, "group": "ЖКХ", "topic": "отопление в домах", "agency": "МинЖКХ"},
        {"id": "3", "severity": 2, "group": "Дороги", "topic": "ямы", "agency": "Минтранс"},
    ]
    pkgs = build_agency_packages(items)
    assert len(pkgs) == 2
    minzhkh = next(p for p in pkgs if p["agency_name"] == "МинЖКХ")
    assert minzhkh["total"] == 2
    assert len(minzhkh["bundles"]) >= 1


def test_merge_agency_packages_dedupes_items():
    page1 = build_agency_packages([
        {"id": "1", "severity": 4, "group": "ЖКХ", "topic": "отопление", "agency": "МинЖКХ"},
    ])
    page2 = build_agency_packages([
        {"id": "2", "severity": 3, "group": "ЖКХ", "topic": "отопление", "agency": "МинЖКХ"},
    ])
    merged = merge_agency_packages(page1, page2)
    assert merged[0]["total"] == 2
