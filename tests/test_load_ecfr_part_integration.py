from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select

from src.db.models import RegulationPart, RegulationSection
from src.db.session import SessionLocal
from src.ingestion.ecfr_client import fetch_part_xml
from src.ingestion.ecfr_parser import parse_part_xml


AS_OF = date(2026, 3, 30)
TITLE_NUMBER = 21
PART_NUMBER = 211


def test_can_insert_part_211_into_database():
    xml_bytes = fetch_part_xml(title=TITLE_NUMBER, part=PART_NUMBER, as_of_date=AS_OF)
    records = parse_part_xml(xml_bytes, part_number=PART_NUMBER, version_date=AS_OF)

    part_record = next(r for r in records if r.level == 0)
    child_records = [r for r in records if r.level >= 1]

    with SessionLocal() as session:
        # Clean up any old test rows for deterministic behavior.
        existing = session.scalar(
            select(RegulationPart).where(
                RegulationPart.title_number == TITLE_NUMBER,
                RegulationPart.part_number == PART_NUMBER,
                RegulationPart.version_date == AS_OF,
            )
        )

        if existing is not None:
            session.execute(
                delete(RegulationSection).where(RegulationSection.part_id == existing.id)
            )
            session.execute(delete(RegulationPart).where(RegulationPart.id == existing.id))
            session.commit()

        db_part = RegulationPart(
            title_number=TITLE_NUMBER,
            part_number=PART_NUMBER,
            version_date=AS_OF,
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

        inserted_part = session.scalar(
            select(RegulationPart).where(
                RegulationPart.title_number == TITLE_NUMBER,
                RegulationPart.part_number == PART_NUMBER,
                RegulationPart.version_date == AS_OF,
            )
        )
        assert inserted_part is not None

        inserted_sections = session.scalars(
            select(RegulationSection).where(RegulationSection.part_id == inserted_part.id)
        ).all()

        assert len(inserted_sections) > 50
        assert any(s.section_number == "211.68" for s in inserted_sections)