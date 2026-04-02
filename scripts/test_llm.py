from __future__ import annotations

from pydantic import BaseModel

from src.llm import call_llm_structured


class HealthCheckResponse(BaseModel):
    message: str
    ok: bool


def main() -> None:
    result = call_llm_structured(
        system_prompt="You are a precise assistant. Return structured output only.",
        user_prompt="Return a short health check with message='llm working' and ok=true.",
        response_model=HealthCheckResponse,
        model="gpt-4o-mini",
        temperature=0.0,
    )

    print(result)
    print(result.model_dump())


if __name__ == "__main__":
    main()