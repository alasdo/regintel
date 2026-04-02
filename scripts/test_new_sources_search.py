from __future__ import annotations

from src.db.session import SessionLocal
from src.retrieval.embedder import embed_texts
from src.retrieval.search import (
    search_similar_context_chunks_by_corpus,
    search_similar_context_chunks_by_document_codes,
)


def run_corpus_query(question: str, corpus: str) -> None:
    print("=" * 100)
    print(f"Corpus: {corpus}")
    print(f"Question: {question}\n")

    query_embedding = embed_texts([question])[0]

    with SessionLocal() as session:
        rows = search_similar_context_chunks_by_corpus(
            session,
            query_embedding=query_embedding,
            corpus=corpus,
            limit=5,
        )

    for row in rows:
        print(f"{row.document_short_code} — {row.heading or f'Chunk {row.chunk_index}'} (sim: {round(float(row.similarity), 3)})")
        print(row.chunk_text[:700])
        print()


def run_document_query(question: str, corpus: str, document_codes: list[str]) -> None:
    print("=" * 100)
    print(f"Corpus: {corpus}")
    print(f"Documents: {document_codes}")
    print(f"Question: {question}\n")

    query_embedding = embed_texts([question])[0]

    with SessionLocal() as session:
        rows = search_similar_context_chunks_by_document_codes(
            session,
            query_embedding=query_embedding,
            corpus=corpus,
            document_codes=document_codes,
            limit=5,
        )

    for row in rows:
        print(f"{row.document_short_code} — {row.heading or f'Chunk {row.chunk_index}'} (sim: {round(float(row.similarity), 3)})")
        print(row.chunk_text[:700])
        print()


def main() -> None:
    run_corpus_query("What does EU GMP Annex 11 say about computerized systems validation?", "eu_gmp")
    run_corpus_query("What does EU GMP say about documentation and good documentation practices?", "eu_gmp")

    run_document_query(
        "What does ICH Q10 say about pharmaceutical quality systems?",
        "ich",
        ["ICH_Q10"],
    )

    run_document_query(
        "What does ICH Q9(R1) say about quality risk management?",
        "ich",
        ["ICH_Q9R1"],
    )


if __name__ == "__main__":
    main()