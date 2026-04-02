from __future__ import annotations

import argparse

from sqlalchemy import text

from src.db.session import SessionLocal
from src.retrieval.embedder import embed_texts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Semantic search over regulation sections.")
    parser.add_argument("--query", required=True, help="Natural-language search query")
    parser.add_argument("--limit", type=int, default=5, help="Number of results to return")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    query = args.query
    limit = args.limit

    query_embedding = embed_texts([query])[0]

    sql = text(
        """
        SELECT
            section_number,
            title,
            version_date,
            1 - (embedding <=> CAST(:emb AS vector)) AS similarity
        FROM regulation_sections
        WHERE embedding IS NOT NULL
          AND level = 2
        ORDER BY embedding <=> CAST(:emb AS vector)
        LIMIT :limit
        """
    )

    with SessionLocal() as session:
        results = session.execute(
            sql,
            {
                "emb": str(query_embedding),
                "limit": limit,
            },
        )

        print(f"Query: {query}\n")
        for row in results:
            print(
                f"{row.section_number} — {row.title} "
                f"[{row.version_date}] "
                f"(similarity: {row.similarity:.3f})"
            )


if __name__ == "__main__":
    main()