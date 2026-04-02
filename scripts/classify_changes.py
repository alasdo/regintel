from __future__ import annotations

from sqlalchemy import select

from src.analysis.classifier import classify_change
from src.db.models import Change, RegulationSection
from src.db.session import SessionLocal


def main() -> None:
    with SessionLocal() as session:
        changes = session.scalars(
            select(Change)
            .where(Change.change_type.is_(None))
            .order_by(Change.old_date, Change.new_date, Change.section_number)
        ).all()

        if not changes:
            print("No unclassified changes found.")
            return

        for change in changes:
            old_text = ""
            new_text = ""
            title = ""

            if change.old_part_id is not None:
                old_section = session.scalar(
                    select(RegulationSection).where(
                        RegulationSection.part_id == change.old_part_id,
                        RegulationSection.section_number == change.section_number,
                        RegulationSection.level == 2,
                    )
                )
                if old_section is not None:
                    old_text = old_section.full_text
                    title = old_section.title or title

            if change.new_part_id is not None:
                new_section = session.scalar(
                    select(RegulationSection).where(
                        RegulationSection.part_id == change.new_part_id,
                        RegulationSection.section_number == change.section_number,
                        RegulationSection.level == 2,
                    )
                )
                if new_section is not None:
                    new_text = new_section.full_text
                    title = new_section.title or title

            result = classify_change(
                section_number=change.section_number,
                title=title or "",
                old_text=old_text,
                new_text=new_text,
                diff=change.raw_diff,
            )

            change.change_type = result.change_type
            change.severity = result.severity
            change.classification_reason = result.reason

            session.add(change)
            session.commit()

            print("=" * 100)
            print(f"Section: {change.section_number}")
            print(f"Type: {change.change_type}")
            print(f"Severity: {change.severity}")
            print(f"Reason: {change.classification_reason}")
            print()

        print("Finished classifying changes.")


if __name__ == "__main__":
    main()