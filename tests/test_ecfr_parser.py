from datetime import date

from src.ingestion.ecfr_client import fetch_part_xml
from src.ingestion.ecfr_parser import parse_part_xml

AS_OF = date(2026, 3, 30)


def load_records():
    xml_bytes = fetch_part_xml(title=21, part=211, as_of_date=AS_OF)
    return parse_part_xml(xml_bytes, part_number=211, version_date=AS_OF)


def test_parse_part_211_returns_records():
    records = load_records()

    assert records
    assert len(records) > 50


def test_parse_part_211_contains_known_sections():
    records = load_records()
    numbers = {record.section_number for record in records}

    expected = {
        "211",
        "211.1",
        "211.3",
        "211.22",
        "211.25",
        "211.42",
        "211.68",
        "211.100",
        "211.160",
        "211.180",
    }

    missing = expected - numbers
    assert not missing, f"Missing expected sections: {missing}"


def test_all_records_have_required_fields():
    records = load_records()

    for record in records:
        assert record.section_number.strip()
        assert record.full_text.strip()
        assert record.level >= 0
        assert record.version_date == AS_OF


def test_section_211_68_has_expected_shape():
    records = load_records()

    record = next(r for r in records if r.section_number == "211.68")

    assert record.title is not None
    assert "Automatic, mechanical, and electronic equipment" in record.title
    assert record.parent_section_number == "Subpart D—Equipment"
    assert "automatic" in record.full_text.lower()