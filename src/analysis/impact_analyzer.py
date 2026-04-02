from __future__ import annotations

from src.llm import call_llm_structured
from src.prompts.impact import IMPACT_SYSTEM_PROMPT, build_impact_user_prompt
from src.schemas import ImpactAnalysisResult


def format_context_rows(rows) -> str:
    blocks = []

    for row in rows:
        if hasattr(row, "section_number"):
            title = getattr(row, "title", None) or "No title"
            text = getattr(row, "full_text", "")
            label = f"[{row.section_number}] {title}"
        else:
            heading = getattr(row, "heading", None) or f"Context chunk {getattr(row, 'chunk_index', '?')}"
            text = getattr(row, "chunk_text", "")
            label = f"[{heading}]"

        blocks.append(f"{label}\n{text}")

    return "\n\n".join(blocks)


def analyze_impact(
    *,
    section_number: str,
    title: str | None,
    old_text: str | None,
    new_text: str | None,
    diff: str,
    classification_reason: str,
    sibling_rows,
    similar_rows,
    rulemaking_rows,
) -> ImpactAnalysisResult:
    sibling_context = format_context_rows(sibling_rows)
    similar_context = format_context_rows(similar_rows)
    rulemaking_context = format_context_rows(rulemaking_rows)

    user_prompt = build_impact_user_prompt(
    section_number=section_number,
    title=title,
    old_text=old_text,
    new_text=new_text,
    diff=diff,
    classification_reason=classification_reason,
    sibling_context=sibling_context,
    similar_context=similar_context,
    rulemaking_context=rulemaking_context,
)

    return call_llm_structured(
        system_prompt=IMPACT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=ImpactAnalysisResult,
        model="gpt-4o-mini",
        temperature=0.0,
    )