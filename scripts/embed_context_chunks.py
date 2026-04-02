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


def build_embedding_input(chunk: ContextChunk, doc: ContextDocument) -> str:
    heading = f"{chunk.heading}\n" if chunk.heading else ""
    return f"{doc.title}\n{heading}{chunk.chunk_text}".strip()


def main() -> None:
    with SessionLocal() as session:
        rows = session.execute(
            select(ContextChunk, ContextDocument)
            .join(ContextDocument, ContextDocument.id == ContextChunk.document_id)
            .where(ContextChunk.embedding.is_(None))
            .order_by(ContextDocument.corpus, ContextDocument.document_short_code, ContextChunk.chunk_index)
        ).all()

        if not rows:
            print("No context chunks need embeddings.")
            return

        embedded_count = 0

        for batch in batched(rows, BATCH_SIZE):
            texts = [build_embedding_input(chunk, doc) for chunk, doc in batch]
            vectors = embed_texts(texts)

            if len(vectors) != len(batch):
                raise ValueError(
                    f"Embedding count mismatch: got {len(vectors)} vectors for {len(batch)} chunks."
                )

            for (chunk, _doc), vector in zip(batch, vectors):
                chunk.embedding = vector

            session.commit()
            embedded_count += len(batch)
            print(f"Embedded {embedded_count}/{len(rows)} context chunks...")

        print(f"Embedded {embedded_count} context chunks.")


if __name__ == "__main__":
    main()