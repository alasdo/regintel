from __future__ import annotations

from itertools import islice

from sqlalchemy import select

from src.db.models import ContextChunk, ContextDocument
from src.db.session import SessionLocal
from src.retrieval.embedder import embed_texts


BATCH_SIZE = 100


def batched(iterable, size: int):
    iterator = iter(iterable)
    while batch := list(islice(iterator, size)):
        yield batch


def build_embedding_input(chunk: ContextChunk) -> str:
    heading = f"{chunk.heading}\n" if chunk.heading else ""
    return f"{heading}{chunk.chunk_text}".strip()


def main() -> None:
    with SessionLocal() as session:
        stmt = (
            select(ContextChunk)
            .join(ContextDocument, ContextDocument.id == ContextChunk.document_id)
            .where(ContextDocument.source_type == "fda_guidance")
            .where(ContextChunk.embedding.is_(None))
            .order_by(ContextDocument.document_short_code, ContextChunk.chunk_index)
        )

        chunks = session.scalars(stmt).all()

        if not chunks:
            print("No FDA guidance chunks need embeddings.")
            return

        embedded_count = 0

        for batch in batched(chunks, BATCH_SIZE):
            texts = [build_embedding_input(chunk) for chunk in batch]
            vectors = embed_texts(texts)

            if len(vectors) != len(batch):
                raise ValueError(
                    f"Embedding count mismatch: got {len(vectors)} vectors for {len(batch)} chunks."
                )

            for chunk, vector in zip(batch, vectors):
                chunk.embedding = vector

            session.commit()
            embedded_count += len(batch)
            print(f"Embedded {embedded_count}/{len(chunks)} FDA guidance chunks...")

        print(f"Embedded {embedded_count} FDA guidance chunks.")


if __name__ == "__main__":
    main()