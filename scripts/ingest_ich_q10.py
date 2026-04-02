from __future__ import annotations

import io
import re
from datetime import date

import httpx
import pdfplumber
from sqlalchemy import delete, select

from src.db.models import ContextDocument, ContextChunk
from src.db.session import SessionLocal
from src.ingestion.text_utils import fallback_chunk_text, normalize_text


DOCUMENT_SHORT_CODE = "ICH_Q10"
SOURCE_TYPE = "ich_guideline"
CORPUS = "ich"
TITLE = "ICH Q10: Pharmaceutical Quality System"
SOURCE_URL = "https://database.ich.org/sites/default/files/Q10%20Guideline.pdf"
PUBLICATION_DATE = date(2008, 6, 4)


def fetch_pdf_bytes() -> bytes:
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        response = client.get(SOURCE_URL)
        response.raise_for_status()
        return response.content


def fetch_pdf_text() -> str:
    pdf_bytes = fetch_pdf_bytes()

    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(
                x_tolerance=2,
                y_tolerance=3,
                layout=False,
            ) or ""
            if page_text.strip():
                text_parts.append(page_text)

    full_text = "\n\n".join(text_parts).strip()
    if not full_text:
        raise ValueError("Failed to extract text from ICH Q10 PDF.")

    return full_text


def clean_text(text: str) -> str:
    text = normalize_text(text)
    text = text.replace("¶", "\n")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    cleaned_lines = []
    for line in text.splitlines():
        line = line.strip()

        # Drop obvious table-of-contents / dot leader lines
        if re.search(r"\.{4,}\s*\d+\s*$", line):
            continue

        # Drop page-number-only lines
        if re.fullmatch(r"\d+", line):
            continue

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_main_text(full_text: str) -> str:
    """
    Start at the first real body section and avoid the table of contents.
    """
    start_markers = [
        "\n1.1 Introduction",
        "1.1 Introduction",
    ]

    start_idx = -1
    for marker in start_markers:
        idx = full_text.find(marker)
        if idx != -1:
            start_idx = idx
            break

    if start_idx == -1:
        return full_text.strip()

    return full_text[start_idx:].strip()


def chunk_text(text: str) -> list[tuple[str | None, str]]:
    lines = text.splitlines()

    heading_pattern = re.compile(
        r"""^(
            \d+(\.\d+)*\s+.+ |
            Introduction$ |
            Management\ Responsibilities$ |
            Continual\ Improvement$ |
            Process\ Performance\ and\ Product\ Quality\ Monitoring\ System$
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

    if len(chunks) <= 5:
        return fallback_chunk_text(text, chunk_size=1200, overlap=150)

    return chunks


def main() -> None:
    full_text = fetch_pdf_text()
    full_text = clean_text(full_text)
    main_text = extract_main_text(full_text)
    chunks = chunk_text(main_text)

    print(f"Extracted text length: {len(main_text)} characters")
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
            session.execute(delete(ContextChunk).where(ContextChunk.document_id == existing_doc.id))
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