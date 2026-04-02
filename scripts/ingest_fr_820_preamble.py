from __future__ import annotations

import re
from datetime import date

import httpx
from sqlalchemy import delete, select

from src.db.models import ContextDocument, ContextChunk
from src.db.session import SessionLocal


METADATA_URL = "https://www.federalregister.gov/api/v1/documents/2024-01709?publication_date=2024-02-02"
DOCUMENT_SHORT_CODE = "21CFR820"
SOURCE_TYPE = "federal_register_preamble"
TITLE = "Medical Devices; Quality System Regulation Amendments"
SOURCE_URL = "https://www.federalregister.gov/documents/2024/02/02/2024-01709/medical-devices-quality-system-regulation-amendments"
PUBLICATION_DATE = date(2024, 2, 2)


def fetch_metadata() -> dict:
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        response = client.get(METADATA_URL)
        response.raise_for_status()
        return response.json()


def fetch_raw_text(raw_text_url: str) -> str:
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        response = client.get(raw_text_url)
        response.raise_for_status()
        return response.text


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_preamble_text(full_text: str) -> str:
    """
    Keep the explanatory preamble, not the codified amendatory text.

    We start at 'I. Executive Summary' if present.
    We stop before 'List of Subjects' if present.
    """
    start_markers = [
        "I. Executive Summary",
        "Executive Summary",
        "SUPPLEMENTARY INFORMATION:",
    ]
    end_markers = [
        "List of Subjects",
        "PART 4—REGULATION OF COMBINATION PRODUCTS",
        "PART 820—QUALITY MANAGEMENT SYSTEM REGULATION",
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
        raise ValueError("Could not extract preamble text from Federal Register raw text.")

    return extracted


def chunk_text_by_headings(text: str) -> list[tuple[str | None, str]]:
    """
    First-pass heading-aware chunker.
    Splits on common Federal Register heading patterns.
    """
    lines = text.splitlines()

    heading_pattern = re.compile(
        r"""^(
            [IVXLC]+\.\s+.+ |          # I. Executive Summary
            [A-Z]\.\s+.+ |             # A. Purpose of the Final Rule
            \d+\.\s+.+ |               # 1. Control of Records ...
            [A-Z][A-Za-z].+?:$         # SUMMARY:
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

        if heading_pattern.match(clean):
            flush()
            current_heading = clean
            current_lines = [clean]
        else:
            current_lines.append(clean)

    flush()

    # Fallback if heading splitting produced too little.
    if len(chunks) <= 2:
        return fallback_chunk_text(text)

    return chunks


def fallback_chunk_text(text: str, chunk_size: int = 2200, overlap: int = 300) -> list[tuple[str | None, str]]:
    chunks: list[tuple[str | None, str]] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append((None, chunk))
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def main() -> None:
    metadata = fetch_metadata()
    raw_text_url = metadata["raw_text_url"]
    raw_text = fetch_raw_text(raw_text_url)
    raw_text = normalize_text(raw_text)

    preamble_text = extract_preamble_text(raw_text)
    chunks = chunk_text_by_headings(preamble_text)

    print(f"Fetched metadata title: {metadata['title']}")
    print(f"Raw text URL: {raw_text_url}")
    print(f"Extracted preamble length: {len(preamble_text)} characters")
    print(f"Prepared {len(chunks)} chunks")

    with SessionLocal() as session:
        existing_doc = session.scalar(
            select(ContextDocument).where(
                ContextDocument.document_short_code == DOCUMENT_SHORT_CODE,
                ContextDocument.source_type == SOURCE_TYPE,
                ContextDocument.publication_date == PUBLICATION_DATE,
            )
        )

        if existing_doc is not None:
            session.execute(
                delete(ContextChunk).where(ContextChunk.document_id == existing_doc.id)
            )
            session.delete(existing_doc)
            session.commit()

        doc = ContextDocument(
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

        print(f"Inserted 1 context_documents row.")
        print(f"Inserted {len(db_chunks)} context_chunks rows.")


if __name__ == "__main__":
    main()