from __future__ import annotations

from datetime import date

from src.db.models import RegulationPart, RegulationSection
from src.db.session import SessionLocal
from src.ingestion.ecfr_client import fetch_part_xml
from src.ingestion.ecfr_parser import parse_part_xml


def main() -> None:
    as_of = date(2026, 3, 30)
    title_number = 21
    part_number = 211

    xml_bytes = fetch_part_xml(title=title_number, part=part_number, as_of_date=as_of)
    records = parse_part_xml(xml_bytes, part_number=part_number, version_date=as_of)

    if not records:
        raise ValueError("No records were parsed.")

    part_record = next((r for r in records if r.level == 0), None)
    if part_record is None:
        raise ValueError("No part-level record found.")

    section_records = [r for r in records if r.level >= 1]

    with SessionLocal() as session:
        # Optional: prevent duplicate loads for same title/part/version
        existing = (
            session.query(RegulationPart)
            .filter(
                RegulationPart.title_number == title_number,
                RegulationPart.part_number == part_number,
                RegulationPart.version_date == as_of,
            )
            .first()
        )

        if existing:
            print(
                f"Part {title_number} CFR Part {part_number} "
                f"for {as_of.isoformat()} already exists in database."
            )
            return

        db_part = RegulationPart(
            title_number=title_number,
            part_number=part_number,
            version_date=as_of,
            heading=part_record.title,
        )
        session.add(db_part)
        session.flush()  # get db_part.id before inserting child rows

        db_sections = [
            RegulationSection(
                part_id=db_part.id,
                section_number=record.section_number,
                title=record.title,
                level=record.level,
                parent_section_number=record.parent_section_number,
                full_text=record.full_text,
                version_date=record.version_date,
            )
            for record in section_records
        ]

        session.add_all(db_sections)
        session.commit()

        print(f"Inserted 1 regulation_parts row.")
        print(f"Inserted {len(db_sections)} regulation_sections rows.")


if __name__ == "__main__":
    main()