from __future__ import annotations

import io
from datetime import date

import httpx
from pypdf import PdfReader
from sqlalchemy import delete, select

from src.db.models import ContextDocument, ContextChunk
from src.db.session import SessionLocal
from src.ingestion.text_utils import fallback_chunk_text, normalize_text


DOCUMENT_SHORT_CODE = "FDA_PROCESS_VALIDATION"
SOURCE_TYPE = "fda_guidance"
CORPUS = "us_fda"
TITLE = "Process Validation: General Principles and Practices"
SOURCE_URL = "https://www.fda.gov/files/drugs/published/Process-Validation--General-Principles-and-Practices.pdf"
PUBLICATION_DATE = date(2011, 1, 1)


def fetch_pdf_text() -> str:
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        response = client.get(SOURCE_URL)
        response.raise_for_status()
        pdf_bytes = response.content

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            text_parts.append(page_text)

    full_text = "\n\n".join(text_parts).strip()
    if not full_text:
        raise ValueError("Failed to extract text from the FDA process validation PDF.")

    return full_text


def extract_guidance_text(full_text: str) -> str:
    start_markers = [
        "Guidance for Industry",
        "Process Validation: General Principles and Practices",
    ]
    end_markers = [
        "Paperwork Reduction Act of 1995",
        "References",
    ]

    start_idx = 0
    for marker in start_markers:
        idx = full_text.find(marker)
        if idx != -1:
            start_idx = idx
            break

    end_idx = len(full_text)
    for marker in end_markers:
        idx = full_text.find(marker, start_idx)
        if idx != -1:
            end_idx = min(end_idx, idx)

    extracted = full_text[start_idx:end_idx].strip()
    if not extracted:
        raise ValueError("Could not extract main process validation guidance text.")

    return extracted


def chunk_guidance_text(text: str) -> list[tuple[str | None, str]]:
    return fallback_chunk_text(text, chunk_size=2200, overlap=300)


def main() -> None:
    full_text = fetch_pdf_text()
    full_text = normalize_text(full_text)
    guidance_text = extract_guidance_text(full_text)
    chunks = chunk_guidance_text(guidance_text)

    print(f"Extracted guidance text length: {len(guidance_text)} characters")
    print(f"Prepared {len(chunks)} chunks")

    with SessionLocal() as session:
        existing_doc = session.scalar(
            select(ContextDocument).where(
                ContextDocument.document_short_code == DOCUMENT_SHORT_CODE,
                ContextDocument.source_type == SOURCE_TYPE,
                ContextDocument.corpus == CORPUS,
            )
        )

        if existing_doc is not None:
            session.execute(
                delete(ContextChunk).where(ContextChunk.document_id == existing_doc.id)
            )
            session.delete(existing_doc)
            session.commit()

        doc = ContextDocument(
            corpus=CORPUS,
            document_short_code=DOCUMENT_SHORT_CODE,
            source_type=SOURCE_TYPE,
            title=TITLE,
            source_url=SOURCE_URL,
            publication_date=PUBLICATION_DATE,
        )
        session.add(doc)
        session.flush()

        db_chunks = [
            ContextChunk(
                document_id=doc.id,
                chunk_index=i,
                heading=heading,
                chunk_text=chunk_text,
            )
            for i, (heading, chunk_text) in enumerate(chunks)
        ]

        session.add_all(db_chunks)
        session.commit()

        print("Inserted 1 context_documents row.")
        print(f"Inserted {len(db_chunks)} context_chunks rows.")


if __name__ == "__main__":
    main()