from __future__ import annotations

import re

from src.llm import call_llm_structured
from src.prompts.qa import QA_SYSTEM_PROMPT
from src.retrieval.embedder import embed_texts
from src.retrieval.search import (
    search_similar_context_chunks_by_document_codes,
    search_similar_sections_current_only,
)
from src.schemas import QAResponse


def detect_part_filter(question: str) -> list[int]:
    q = question.lower()

    mentioned_parts: list[int] = []

    if re.search(r"\bpart\s*11\b", q) or re.search(r"\b21\s*cfr\s*11\b", q):
        mentioned_parts.append(11)

    if re.search(r"\bpart\s*210\b", q) or re.search(r"\b21\s*cfr\s*210\b", q):
        mentioned_parts.append(210)

    if re.search(r"\bpart\s*211\b", q) or re.search(r"\b21\s*cfr\s*211\b", q):
        mentioned_parts.extend([210, 211])

    if re.search(r"\bpart\s*820\b", q) or re.search(r"\b21\s*cfr\s*820\b", q):
        mentioned_parts.append(820)

    deduped: list[int] = []
    for p in mentioned_parts:
        if p not in deduped:
            deduped.append(p)

    return deduped or [11, 210, 211, 820]


def detect_fda_guidance_source_types(question: str) -> list[str]:
    q = question.lower()
    docs: list[str] = []

    if "data integrity" in q or "cgmp records" in q or "record integrity" in q:
        docs.append("FDA_DATA_INTEGRITY")

    if "process validation" in q or "validation lifecycle" in q:
        docs.append("FDA_PROCESS_VALIDATION")

    if "aseptic" in q or "sterile" in q or "sterility assurance" in q:
        docs.append("FDA_ASEPTIC_PROCESSING")

    if "quality systems approach" in q or "quality system" in q or "pharmaceutical quality system" in q:
        docs.append("FDA_QUALITY_SYSTEMS")

    if "guidance" in q and not docs:
        docs.extend([
            "FDA_DATA_INTEGRITY",
            "FDA_PROCESS_VALIDATION",
            "FDA_ASEPTIC_PROCESSING",
            "FDA_QUALITY_SYSTEMS",
        ])

    deduped: list[str] = []
    for d in docs:
        if d not in deduped:
            deduped.append(d)

    return deduped


def format_context(reg_sections, guidance_chunks) -> str:
    blocks = []

    for s in reg_sections:
        blocks.append(f"[Section {s.section_number}] {s.title or ''}\n{s.full_text}")

    for g in guidance_chunks:
        blocks.append(f"[Guidance: {g.document_short_code}] {g.heading or ''}\n{g.chunk_text}")

    return "\n\n---\n\n".join(blocks)


def build_retry_user_prompt(question: str, valid_sections: set[str]) -> str:
    allowed = ", ".join(sorted(valid_sections))
    return (
        f"{question}\n\n"
        f"You must cite ONLY from these retrieved source identifiers: {allowed}. "
        f"If the retrieved context is insufficient, say so clearly."
    )


def validate_and_enrich_citations(response: QAResponse, valid_sections: set[str]) -> tuple[list[dict], bool]:
    enriched_citations = []
    any_invalid = False

    for cit in response.citations:
        is_valid = cit.section_number in valid_sections
        if not is_valid:
            any_invalid = True

        enriched_citations.append(
            {
                "section_number": cit.section_number,
                "relevance": cit.relevance,
                "valid": is_valid,
            }
        )

    return enriched_citations, any_invalid


def ask(session, question: str, top_k: int = 7, guidance_k: int = 3) -> dict:
    query_embedding = embed_texts([question])[0]
    part_numbers = detect_part_filter(question)

    reg_results = search_similar_sections_current_only(
        session,
        query_embedding=query_embedding,
        limit=top_k,
        part_numbers=part_numbers,
    )

    guidance_results = []
    guidance_docs = detect_fda_guidance_source_types(question)
    if guidance_docs:
        guidance_results = search_similar_context_chunks_by_document_codes(
            session,
            query_embedding=query_embedding,
            corpus="us_fda",
            document_codes=guidance_docs,
            limit=guidance_k,
        )

    if not reg_results and not guidance_results:
        return {
            "answer": "No relevant sources were found for this question.",
            "citations": [],
            "confidence": "low",
            "retrieved_sections": [],
            "retrieved_guidance": [],
            "part_filter": part_numbers,
            "retried_for_citations": False,
        }

    context = format_context(reg_results, guidance_results)
    system_prompt = QA_SYSTEM_PROMPT.format(context=context)

    response = call_llm_structured(
        system_prompt=system_prompt,
        user_prompt=question,
        response_model=QAResponse,
        model="gpt-4o-mini",
        temperature=0.0,
    )

    valid_sections = {r.section_number for r in reg_results}
    valid_sections.update({f"Guidance: {g.document_short_code}" for g in guidance_results})

    enriched_citations, any_invalid = validate_and_enrich_citations(response, valid_sections)
    retried = False

    if any_invalid:
        retried = True
        retry_prompt = build_retry_user_prompt(question=question, valid_sections=valid_sections)

        response = call_llm_structured(
            system_prompt=system_prompt,
            user_prompt=retry_prompt,
            response_model=QAResponse,
            model="gpt-4o-mini",
            temperature=0.0,
        )

        enriched_citations, any_invalid = validate_and_enrich_citations(response, valid_sections)

    return {
        "answer": response.answer,
        "citations": enriched_citations,
        "confidence": response.confidence,
        "retrieved_sections": [
            {
                "section_number": r.section_number,
                "title": r.title,
                "version_date": str(r.version_date),
                "similarity": round(float(r.similarity), 3),
            }
            for r in reg_results
        ],
        "retrieved_guidance": [
            {
                "document_short_code": g.document_short_code,
                "heading": g.heading or f"Chunk {g.chunk_index}",
                "similarity": round(float(g.similarity), 3),
            }
            for g in guidance_results
        ],
        "part_filter": part_numbers,
        "retried_for_citations": retried,
    }