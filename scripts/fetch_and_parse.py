from datetime import date

from src.ingestion.ecfr_client import fetch_part_xml
from src.ingestion.ecfr_parser import parse_part_xml


def main() -> None:
    """
    Manual preview script for fetching and parsing 21 CFR Part 211.

    This is intentionally separate from pytest tests so you can quickly inspect
    parsed records during development.
    """
    as_of = date(2026, 3, 30)

    xml_bytes = fetch_part_xml(title=21, part=211, as_of_date=as_of)
    records = parse_part_xml(xml_bytes, part_number=211, version_date=as_of)

    print(f"Fetched XML for 21 CFR Part 211 as of {as_of.isoformat()}")
    print(f"Parsed {len(records)} records\n")

    print("First 15 records:")
    for record in records[:15]:
        print("-" * 100)
        print(f"section_number: {record.section_number}")
        print(f"title: {record.title}")
        print(f"level: {record.level}")
        print(f"parent: {record.parent_section_number}")
        print(f"text preview: {record.full_text[:500]}")

    print("\nKnown section spot-checks:")
    targets = {"211.1", "211.22", "211.42", "211.68", "211.100", "211.160", "211.180"}
    for record in records:
        if record.section_number in targets:
            print("-" * 100)
            print(f"{record.section_number} | {record.title}")
            print(f"parent: {record.parent_section_number}")
            print(f"text preview: {record.full_text[:400]}")

    print("\nRecord counts by level:")
    counts: dict[int, int] = {}
    for record in records:
        counts[record.level] = counts.get(record.level, 0) + 1

    for level in sorted(counts):
        print(f"level {level}: {counts[level]} records")


if __name__ == "__main__":
    main()