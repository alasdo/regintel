from __future__ import annotations

from src.db.session import SessionLocal
from src.retrieval.embedder import embed_texts
from src.retrieval.search import search_similar_context_chunks


def main() -> None:
    query = "why were old Part 820 sections removed and replaced by ISO 13485"
    query_embedding = embed_texts([query])[0]

    with SessionLocal() as session:
        rows = search_similar_context_chunks(
            session,
            query_embedding=query_embedding,
            document_short_code="21CFR820",
            limit=5,
        )

        print(f"Query: {query}\n")
        for row in rows:
            print("=" * 100)
            print(f"chunk_index: {row.chunk_index}")
            print(f"heading: {row.heading}")
            print(f"similarity: {row.similarity:.3f}")
            print(row.chunk_text[:1000])
            print()


if __name__ == "__main__":
    main()