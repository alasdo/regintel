from __future__ import annotations

import argparse
from datetime import date

from sqlalchemy import select

from src.db.models import Change, RegulationPart, RegulationSection
from src.db.session import SessionLocal
from src.versioning.differ import diff_versions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect changes between two eCFR part snapshots.")
    parser.add_argument("--title", type=int, required=True, help="CFR title number, e.g. 21")
    parser.add_argument("--part", type=int, required=True, help="CFR part number, e.g. 211")
    parser.add_argument("--from-date", dest="from_date", required=True, help="Old date YYYY-MM-DD")
    parser.add_argument("--to-date", dest="to_date", required=True, help="New date YYYY-MM-DD")
    return parser.parse_args()


def load_part_for_date(session, *, title_number: int, part_number: int, version_date: date) -> RegulationPart:
    part = session.scalar(
        select(RegulationPart).where(
            RegulationPart.title_number == title_number,
            RegulationPart.part_number == part_number,
            RegulationPart.version_date == version_date,
        )
    )
    if part is None:
        raise ValueError(
            f"No regulation_parts row found for title={title_number}, "
            f"part={part_number}, version_date={version_date}"
        )
    return part


def load_sections_for_part(session, *, part_id: int) -> list[RegulationSection]:
    return session.scalars(
        select(RegulationSection)
        .where(
            RegulationSection.part_id == part_id,
            RegulationSection.level == 2,
        )
        .order_by(RegulationSection.section_number)
    ).all()


def main() -> None:
    args = parse_args()

    title_number = args.title
    part_number = args.part
    old_date = date.fromisoformat(args.from_date)
    new_date = date.fromisoformat(args.to_date)
    document_short_code = f"{title_number}CFR{part_number}"

    with SessionLocal() as session:
        old_part = load_part_for_date(
            session,
            title_number=title_number,
            part_number=part_number,
            version_date=old_date,
        )
        new_part = load_part_for_date(
            session,
            title_number=title_number,
            part_number=part_number,
            version_date=new_date,
        )

        old_sections = load_sections_for_part(session, part_id=old_part.id)
        new_sections = load_sections_for_part(session, part_id=new_part.id)

        changes = diff_versions(old_sections, new_sections)

        print(f"Comparing {document_short_code}: {old_date} -> {new_date}")
        print(f"Loaded {len(old_sections)} old sections and {len(new_sections)} new sections")
        print()

        for change in changes[:10]:
            print("=" * 100)
            print(f"SECTION: {change['section_number']}")
            print(f"TYPE: {change['type']}")
            print(change["raw_diff"][:2000])
            print()

        modified = 0
        added = 0
        removed = 0

        for change in changes:
            if change["type"] == "modified":
                modified += 1
                old_part_id = old_part.id
                new_part_id = new_part.id
            elif change["type"] == "added":
                added += 1
                old_part_id = None
                new_part_id = new_part.id
            else:
                removed += 1
                old_part_id = old_part.id
                new_part_id = None

            existing = session.scalar(
                select(Change).where(
                    Change.document_short_code == document_short_code,
                    Change.section_number == change["section_number"],
                    Change.old_date == old_date,
                    Change.new_date == new_date,
                )
            )

            if existing is not None:
                continue

            session.add(
                Change(
                    document_short_code=document_short_code,
                    section_number=change["section_number"],
                    old_part_id=old_part_id,
                    new_part_id=new_part_id,
                    old_date=old_date,
                    new_date=new_date,
                    raw_diff=change["raw_diff"],
                )
            )

        session.commit()

        print(f"Found {modified} modified, {added} added, {removed} removed sections.")
        print(f"Stored {len(changes)} total change records (minus any already existing rows).")


if __name__ == "__main__":
    main()