from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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