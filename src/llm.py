from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env", override=True)

client = OpenAI()

T = TypeVar("T", bound=BaseModel)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def call_llm_structured(
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
) -> T:
    """
    Call OpenAI with structured output parsing into a Pydantic model.
    """
    completion = client.beta.chat.completions.parse(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format=response_model,
    )

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("Model returned no parsed structured output.")

    return parsed