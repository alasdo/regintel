from __future__ import annotations

import re
from datetime import date

import httpx
from sqlalchemy import delete, select

from src.db.models import ContextDocument, ContextChunk
from src.db.session import SessionLocal
from src.ingestion.text_utils import fallback_chunk_text, normalize_text


DOCUMENT_SHORT_CODE = "FDA_DATA_INTEGRITY"
SOURCE_TYPE = "fda_guidance"
CORPUS = "us_fda"
TITLE = "Data Integrity and Compliance With Drug CGMP: Questions and Answers"
SOURCE_URL = "https://www.fda.gov/media/119267/download"
PUBLICATION_DATE = date(2018, 12, 1)  # guidance PDF date is approximated here for storage


def fetch_pdf_text() -> str:
    """
    Simple text extraction path using the FDA PDF converted via pypdf.
    """
    import io
    from pypdf import PdfReader

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
        raise ValueError("Failed to extract text from the FDA guidance PDF.")

    return full_text


def extract_guidance_text(full_text: str) -> str:
    """
    Keep the main body of the guidance and remove obvious boilerplate if present.
    """
    start_markers = [
        "Data Integrity and Compliance With Drug CGMP",
        "Questions and Answers",
        "Contains Nonbinding Recommendations",
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
        raise ValueError("Could not extract main guidance text.")

    return extracted


def chunk_guidance_by_questions(text: str) -> list[tuple[str | None, str]]:
    """
    Chunk around Q&A style headings where possible.
    """
    lines = text.splitlines()

    heading_pattern = re.compile(
        r"""^(
            Q\d+\..+ |
            Question\s+\d+.* |
            [A-Z][A-Za-z0-9 ,\-/()]+$
        )$""",
        re.VERBOSE,
    )

    chunks: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush():
        nonlocal current_heading, current_lines
        body = "\n".join(current_lines).strip()
        if body:
            chunks.append((current_heading, body))
        current_lines = []

    for line in lines:
        clean = line.strip()
        if not clean:
            current_lines.append("")
            continue

        if heading_pattern.match(clean) and len(clean) < 180:
            flush()
            current_heading = clean
            current_lines = [clean]
        else:
            current_lines.append(clean)

    flush()

    if len(chunks) <= 3:
        return fallback_chunk_text(text)

    return chunks


def main() -> None:
    full_text = fetch_pdf_text()
    full_text = normalize_text(full_text)
    guidance_text = extract_guidance_text(full_text)
    chunks = chunk_guidance_by_questions(guidance_text)

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