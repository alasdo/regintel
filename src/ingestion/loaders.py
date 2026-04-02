from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import RegulationPart, RegulationSection
from src.ingestion.ecfr_client import fetch_part_xml
from src.ingestion.ecfr_parser import parse_part_xml


def load_ecfr_part(
    session: Session,
    *,
    title_number: int,
    part_number: int,
    version_date: date,
) -> tuple[RegulationPart, int, bool]:
    """
    Load one CFR part into the database.

    Returns:
        (db_part, inserted_section_count, created_new)
    """
    existing = session.scalar(
        select(RegulationPart).where(
            RegulationPart.title_number == title_number,
            RegulationPart.part_number == part_number,
            RegulationPart.version_date == version_date,
        )
    )
    if existing is not None:
        return existing, 0, False

    xml_bytes = fetch_part_xml(title=title_number, part=part_number, as_of_date=version_date)
    records = parse_part_xml(xml_bytes, part_number=part_number, version_date=version_date)

    part_record = next((r for r in records if r.level == 0), None)
    if part_record is None:
        raise ValueError("No part-level record found.")

    child_records = [r for r in records if r.level >= 1]

    db_part = RegulationPart(
        title_number=title_number,
        part_number=part_number,
        version_date=version_date,
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

    return db_part, len(db_sections), True