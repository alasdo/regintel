from __future__ import annotations

from openai import OpenAI

from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env", override=True)

client = OpenAI()


def embed_texts(
    texts: list[str],
    model: str = "text-embedding-3-small",
) -> list[list[float]]:
    """
    Embed a list of texts and return a list of embedding vectors.
    """
    if not texts:
        return []

    response = client.embeddings.create(
        model=model,
        input=texts,
    )
    return [item.embedding for item in response.data]