from __future__ import annotations

import sys

from src.db.session import SessionLocal
from src.llm import call_llm_structured
from src.prompts.qa import QA_SYSTEM_PROMPT
from src.retrieval.embedder import embed_texts
from src.retrieval.search import search_similar_context_chunks_by_corpus
from src.schemas import QAResponse


def format_context(guidance_chunks) -> str:
    blocks = []
    for g in guidance_chunks:
        blocks.append(f"[Guidance: {g.document_short_code}] {g.heading or f'Chunk {g.chunk_index}'}\n{g.chunk_text}")
    return "\n\n---\n\n".join(blocks)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: uv run python -m scripts.ask_eu 'your question here'")
        raise SystemExit(1)

    question = " ".join(sys.argv[1:])
    query_embedding = embed_texts([question])[0]

    with SessionLocal() as session:
        rows = search_similar_context_chunks_by_corpus(
            session,
            query_embedding=query_embedding,
            corpus="eu_gmp",
            limit=5,
        )

    if not rows:
        print("No relevant EU GMP context found.")
        raise SystemExit(0)

    context = format_context(rows)
    system_prompt = QA_SYSTEM_PROMPT.format(context=context)

    response = call_llm_structured(
        system_prompt=system_prompt,
        user_prompt=question,
        response_model=QAResponse,
        model="gpt-4o-mini",
        temperature=0.0,
    )

    print("=" * 80)
    print("ANSWER")
    print("=" * 80)
    print(response.answer)
    print()
    print("CITATIONS")
    for cit in response.citations:
        print(f"  {cit.section_number}: {cit.relevance}")
    print()
    print(f"Confidence: {response.confidence}")
    print()
    print("RETRIEVED EU CONTEXT")
    for r in rows:
        print(f"  {r.document_short_code} — {r.heading or f'Chunk {r.chunk_index}'} (sim: {round(float(r.similarity), 3)})")


if __name__ == "__main__":
    main()