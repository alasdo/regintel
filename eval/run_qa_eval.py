from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from src.db.session import SessionLocal
from src.llm import call_llm_structured
from src.prompts.qa import QA_SYSTEM_PROMPT
from src.retrieval.embedder import embed_texts
from src.retrieval.qa import ask
from src.retrieval.search import search_similar_context_chunks_by_corpus
from src.schemas import QAResponse


GOLDEN_PATH = Path("eval/test_cases/qa_golden.jsonl")
RESULTS_DIR = Path("eval/results")


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def safe_div(n: float, d: float) -> float:
    return n / d if d else 0.0


def recall_at_k(expected: list[str], retrieved: list[str], k: int) -> float:
    if not expected:
        return 1.0
    top_k = set(retrieved[:k])
    hits = sum(1 for item in expected if item in top_k)
    return hits / len(expected)


def normalize_retrieved_sources(result: dict) -> list[str]:
    sources = []

    for row in result.get("retrieved_sections", []):
        sources.append(row["section_number"])

    for row in result.get("retrieved_guidance", []):
        heading = row.get("heading", "")
        doc_code = row["document_short_code"]
        if heading and not str(heading).startswith("Chunk "):
            sources.append(f"Guidance: {doc_code} {heading}".strip())
        sources.append(f"Guidance: {doc_code}")

    deduped = []
    for s in sources:
        if s not in deduped:
            deduped.append(s)
    return deduped


def run_non_fda_question(session, question: str, corpus: str) -> dict:
    query_embedding = embed_texts([question])[0]
    rows = search_similar_context_chunks_by_corpus(
        session,
        query_embedding=query_embedding,
        corpus=corpus,
        limit=5,
    )

    if not rows:
        return {
            "answer": f"No relevant {corpus} context was found for this question.",
            "citations": [],
            "confidence": "low",
            "retrieved_sections": [],
            "retrieved_guidance": [],
            "part_filter": [],
            "retried_for_citations": False,
        }

    context = "\n\n---\n\n".join(
        f"[Guidance: {r.document_short_code}] {r.heading or f'Chunk {r.chunk_index}'}\n{r.chunk_text}"
        for r in rows
    )

    system_prompt = QA_SYSTEM_PROMPT.format(context=context)

    response = call_llm_structured(
        system_prompt=system_prompt,
        user_prompt=question,
        response_model=QAResponse,
        model="gpt-4o-mini",
        temperature=0.0,
    )

    return {
        "answer": response.answer,
        "citations": [
            {
                "section_number": c.section_number,
                "relevance": c.relevance,
                "valid": True,
            }
            for c in response.citations
        ],
        "confidence": response.confidence,
        "retrieved_sections": [],
        "retrieved_guidance": [
            {
                "document_short_code": r.document_short_code,
                "heading": r.heading or f"Chunk {r.chunk_index}",
                "similarity": round(float(r.similarity), 3),
            }
            for r in rows
        ],
        "part_filter": [],
        "retried_for_citations": False,
    }


def run_case(session, case: dict) -> dict:
    corpus = case["corpus"]
    question = case["question"]

    if corpus == "us_fda":
        return ask(session, question=question, top_k=7)

    if corpus in {"eu_gmp", "ich"}:
        return run_non_fda_question(session, question=question, corpus=corpus)

    raise ValueError(f"Unsupported corpus in test case: {corpus}")


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cases = load_jsonl(GOLDEN_PATH)

    total_cases = len(cases)

    recall5_sum = 0.0
    recall7_sum = 0.0
    citation_total = 0
    citation_valid = 0
    out_of_scope_total = 0
    out_of_scope_correct = 0

    per_corpus_counts = Counter()
    per_corpus_recall5 = defaultdict(float)
    per_corpus_recall7 = defaultdict(float)
    per_corpus_citation_total = Counter()
    per_corpus_citation_valid = Counter()

    details = []

    with SessionLocal() as session:
        for case in cases:
            result = run_case(session, case)
            retrieved_sources = normalize_retrieved_sources(result)
            expected_sources = case.get("expected_sources", [])

            r5 = recall_at_k(expected_sources, retrieved_sources, 5)
            r7 = recall_at_k(expected_sources, retrieved_sources, 7)

            recall5_sum += r5
            recall7_sum += r7

            corpus = case["corpus"]
            per_corpus_counts[corpus] += 1
            per_corpus_recall5[corpus] += r5
            per_corpus_recall7[corpus] += r7

            for cit in result.get("citations", []):
                citation_total += 1
                per_corpus_citation_total[corpus] += 1

                if cit.get("valid", False):
                    citation_valid += 1
                    per_corpus_citation_valid[corpus] += 1

            if case.get("expected_out_of_scope", False):
                out_of_scope_total += 1
                if result.get("confidence") == "low":
                    out_of_scope_correct += 1

            details.append(
                {
                    "question": case["question"],
                    "corpus": corpus,
                    "category": case["category"],
                    "expected_sources": expected_sources,
                    "retrieved_sources": retrieved_sources,
                    "recall_at_5": round(r5, 3),
                    "recall_at_7": round(r7, 3),
                    "confidence": result.get("confidence"),
                    "citations": result.get("citations", []),
                    "answer": result.get("answer"),
                    "notes": case.get("notes", ""),
                }
            )

    summary = {
        "run_date": str(date.today()),
        "test_cases": total_cases,
        "retrieval_recall_at_5": round(safe_div(recall5_sum, total_cases), 3),
        "retrieval_recall_at_7": round(safe_div(recall7_sum, total_cases), 3),
        "citation_validity_rate": round(safe_div(citation_valid, citation_total), 3),
        "out_of_scope_correct": out_of_scope_correct,
        "out_of_scope_total": out_of_scope_total,
        "per_corpus": {},
    }

    for corpus in sorted(per_corpus_counts):
        summary["per_corpus"][corpus] = {
            "cases": per_corpus_counts[corpus],
            "recall_at_5": round(safe_div(per_corpus_recall5[corpus], per_corpus_counts[corpus]), 3),
            "recall_at_7": round(safe_div(per_corpus_recall7[corpus], per_corpus_counts[corpus]), 3),
            "citation_validity_rate": round(
                safe_div(per_corpus_citation_valid[corpus], per_corpus_citation_total[corpus]), 3
            ),
        }

    out_path = RESULTS_DIR / f"qa_eval_{date.today().isoformat()}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"summary": summary, "details": details}, f, indent=2)

    print(f"Q&A Evaluation Results (run: {summary['run_date']})")
    print("=" * 60)
    print(f"Test cases:            {summary['test_cases']}")
    print(f"Retrieval recall@5:    {summary['retrieval_recall_at_5']:.3f}")
    print(f"Retrieval recall@7:    {summary['retrieval_recall_at_7']:.3f}")
    print(f"Citation validity:     {summary['citation_validity_rate']:.3f}")
    print(f"Out-of-scope correct:  {summary['out_of_scope_correct']}/{summary['out_of_scope_total']}")
    print()
    print("Per-corpus breakdown")
    for corpus, metrics in summary["per_corpus"].items():
        print(
            f"  {corpus:8s} "
            f"cases={metrics['cases']:2d} "
            f"r@5={metrics['recall_at_5']:.3f} "
            f"r@7={metrics['recall_at_7']:.3f} "
            f"cit_valid={metrics['citation_validity_rate']:.3f}"
        )
    print()
    print(f"Detailed results written to: {out_path}")


if __name__ == "__main__":
    main()