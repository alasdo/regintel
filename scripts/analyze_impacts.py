from __future__ import annotations

from sqlalchemy import select

from src.analysis.impact_analyzer import analyze_impact
from src.db.models import Change, ImpactAnalysis, RegulationSection
from src.db.session import SessionLocal
from src.retrieval.embedder import embed_texts
from src.retrieval.search import (
    get_sibling_sections,
    search_similar_context_chunks,
    search_similar_sections,
)


def main() -> None:
    with SessionLocal() as session:
        changes = session.scalars(
            select(Change)
            .where(Change.change_type == "substantive")
            .order_by(Change.old_date, Change.new_date, Change.section_number)
        ).all()

        for change in changes:
            existing = session.scalar(
                select(ImpactAnalysis).where(ImpactAnalysis.change_id == change.id)
            )
            if existing is not None:
                continue

            old_section = None
            new_section = None

            if change.old_part_id is not None:
                old_section = session.scalar(
                    select(RegulationSection).where(
                        RegulationSection.part_id == change.old_part_id,
                        RegulationSection.section_number == change.section_number,
                        RegulationSection.level == 2,
                    )
                )

            if change.new_part_id is not None:
                new_section = session.scalar(
                    select(RegulationSection).where(
                        RegulationSection.part_id == change.new_part_id,
                        RegulationSection.section_number == change.section_number,
                        RegulationSection.level == 2,
                    )
                )

            title = (
                (new_section.title if new_section else None)
                or (old_section.title if old_section else None)
            )
            old_text = old_section.full_text if old_section else None
            new_text = new_section.full_text if new_section else None

            retrieval_query = f"{change.section_number} {title or ''} compliance impact regulatory context"
            query_embedding = embed_texts([retrieval_query])[0]

            part_id_for_context = change.new_part_id or change.old_part_id
            sibling_rows = get_sibling_sections(
                session,
                section_number=change.section_number,
                part_id=part_id_for_context,
            )

            similar_rows = search_similar_sections(
                session,
                query_embedding=query_embedding,
                limit=5,
                exclude_section_numbers=[change.section_number],
            )

            rulemaking_rows = []
            if change.document_short_code == "21CFR820":
                rulemaking_rows = search_similar_context_chunks(
                    session,
                    query_embedding=query_embedding,
                    document_short_code="21CFR820",
                    source_type="federal_register_preamble",
                    limit=3,
                )

            result = analyze_impact(
                section_number=change.section_number,
                title=title,
                old_text=old_text,
                new_text=new_text,
                diff=change.raw_diff,
                classification_reason=change.classification_reason or "",
                sibling_rows=sibling_rows,
                similar_rows=similar_rows,
                rulemaking_rows=rulemaking_rows,
            )

            session.add(
                ImpactAnalysis(
                    change_id=change.id,
                    summary=result.summary,
                    what_changed=result.what_changed,
                    affected_functions=result.affected_functions,
                    affected_processes=result.affected_processes,
                    recommended_action=result.recommended_action,
                    action_details=result.action_details,
                    confidence=result.confidence,
                    citations=[c.model_dump() for c in result.citations],
                    model_used="gpt-4o-mini",
                )
            )
            session.commit()

            print("=" * 100)
            print(f"Section: {change.section_number}")
            print(f"Summary: {result.summary}")
            print(f"Action: {result.recommended_action}")
            print(f"Confidence: {result.confidence}")
            print(f"Affected functions: {result.affected_functions}")
            print(f"Affected processes: {result.affected_processes}")
            print()

        print("Finished impact analysis generation.")


if __name__ == "__main__":
    main()