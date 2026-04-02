from __future__ import annotations

from itertools import islice

from sqlalchemy import select

from src.db.models import RegulationSection
from src.db.session import SessionLocal
from src.retrieval.embedder import embed_texts


BATCH_SIZE = 100


def batched(iterable, size: int):
    iterator = iter(iterable)
    while batch := list(islice(iterator, size)):
        yield batch


def build_embedding_input(section: RegulationSection) -> str:
    title = section.title or ""
    return f"21 CFR {section.section_number} — {title}: {section.full_text}".strip()


def main() -> None:
    with SessionLocal() as session:
        sections = session.scalars(
            select(RegulationSection)
            .where(RegulationSection.embedding.is_(None))
            .order_by(RegulationSection.id)
        ).all()

        if not sections:
            print("No sections need embeddings.")
            return

        embedded_count = 0

        for batch in batched(sections, BATCH_SIZE):
            texts = [build_embedding_input(section) for section in batch]
            vectors = embed_texts(texts)

            if len(vectors) != len(batch):
                raise ValueError(
                    f"Embedding count mismatch: got {len(vectors)} vectors for {len(batch)} sections."
                )

            for section, vector in zip(batch, vectors):
                section.embedding = vector

            session.commit()
            embedded_count += len(batch)
            print(f"Embedded {embedded_count}/{len(sections)} sections...")

        print(f"Embedded {embedded_count} sections.")
        

if __name__ == "__main__":
    main()