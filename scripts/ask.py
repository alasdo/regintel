"""Ask a regulatory question.

Usage:
    uv run python -m scripts.ask "your question here"
"""
from __future__ import annotations

import sys

from src.db.session import SessionLocal
from src.retrieval.qa import ask


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: uv run python -m scripts.ask 'What are the requirements for...?'")
        raise SystemExit(1)

    question = " ".join(sys.argv[1:])

    with SessionLocal() as session:
        print(f"Question: {question}\n")
        print("Retrieving relevant sections...\n")

        result = ask(session, question)

    print("=" * 80)
    print("ANSWER:")
    print("=" * 80)
    print(result["answer"])
    print()

    print("CITATIONS:")
    for cit in result["citations"]:
        status = "✓" if cit.get("valid", False) else "✗ INVALID"
        print(f"  [{status}] Section {cit['section_number']}: {cit.get('relevance', '')}")
    print()

    print(f"Confidence: {result['confidence']}")
    print(f"Part filter used: {result['part_filter']}")
    print(f"Retried for invalid citations: {result['retried_for_citations']}")
    print()

    print("RETRIEVED SECTIONS (by similarity):")
    for s in result["retrieved_sections"]:
        print(
            f"  {s['section_number']} — {s['title']} "
            f"[{s['version_date']}] "
            f"(sim: {s['similarity']})"
        )
    
    print()
    print("RETRIEVED GUIDANCE:")
    for g in result.get("retrieved_guidance", []):
        print(
            f"  {g['document_short_code']} — {g['heading']} "
            f"(sim: {g['similarity']})"
        )


if __name__ == "__main__":
    main()