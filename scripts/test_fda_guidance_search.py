from __future__ import annotations

from src.db.session import SessionLocal
from src.retrieval.embedder import embed_texts
from src.retrieval.search import search_similar_context_chunks_by_source_type


def main() -> None:
    query = "What does FDA guidance say about data integrity and complete records?"
    query_embedding = embed_texts([query])[0]

    with SessionLocal() as session:
        rows = search_similar_context_chunks_by_source_type(
            session,
            query_embedding=query_embedding,
            corpus="us_fda",
            source_type="fda_guidance",
            limit=5,
        )

        print(f"Query: {query}\n")
        for row in rows:
            print("=" * 100)
            print(f"document_short_code: {row.document_short_code}")
            print(f"chunk_index: {row.chunk_index}")
            print(f"heading: {row.heading}")
            print(f"similarity: {row.similarity:.3f}")
            print(row.chunk_text[:1000])
            print()


if __name__ == "__main__":
    main()