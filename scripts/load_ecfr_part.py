from __future__ import annotations

import argparse
from datetime import date

from sqlalchemy import select

from src.db.models import RegulationPart, RegulationSection
from src.db.session import SessionLocal
from src.ingestion.ecfr_client import fetch_part_xml
from src.ingestion.ecfr_parser import parse_part_xml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load one eCFR part into the database."
    )
    parser.add_argument("--title", type=int, required=True, help="CFR title number, e.g. 21")
    parser.add_argument("--part", type=int, required=True, help="CFR part number, e.g. 211")
    parser.add_argument(
        "--date",
        dest="as_of_date",
        type=str,
        required=True,
        help="Version date in YYYY-MM-DD format",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    title_number = args.title
    part_number = args.part
    as_of = date.fromisoformat(args.as_of_date)

    xml_bytes = fetch_part_xml(title=title_number, part=part_number, as_of_date=as_of)
    records = parse_part_xml(xml_bytes, part_number=part_number, version_date=as_of)

    if not records:
        raise ValueError("No records were parsed.")

    part_record = next((r for r in records if r.level == 0), None)
    if part_record is None:
        raise ValueError("No part-level record found.")

    child_records = [r for r in records if r.level >= 1]

    with SessionLocal() as session:
        existing = session.scalar(
            select(RegulationPart).where(
                RegulationPart.title_number == title_number,
                RegulationPart.part_number == part_number,
                RegulationPart.version_date == as_of,
            )
        )

        if existing is not None:
            print(
                f"Already loaded: title={title_number}, part={part_number}, "
                f"version_date={as_of.isoformat()}."
            )
            return

        db_part = RegulationPart(
            title_number=title_number,
            part_number=part_number,
            version_date=as_of,
            heading=part_record.title,
        )
        session.add(db_part)
        session.flush()

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
            for record in child_records
        ]

        session.add_all(db_sections)
        session.commit()

        print(
            f"Inserted part title={title_number} part={part_number} "
            f"version_date={as_of.isoformat()}"
        )
        print(f"Inserted {len(db_sections)} regulation_sections rows.")


if __name__ == "__main__":
    main()