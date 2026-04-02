from __future__ import annotations

from src.llm import call_llm_structured
from src.prompts.classification import CLASSIFICATION_SYSTEM_PROMPT
from src.schemas import ChangeClassification


def classify_change(
    section_number: str,
    title: str,
    old_text: str,
    new_text: str,
    diff: str,
) -> ChangeClassification:
    user_prompt = f"""Section: {section_number} — {title}

OLD TEXT:
{old_text}

NEW TEXT:
{new_text}

DIFF:
{diff}"""

    return call_llm_structured(
        system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=ChangeClassification,
        model="gpt-4o-mini",
        temperature=0.0,
    )