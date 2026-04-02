from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import text

from src.db.session import SessionLocal
from src.retrieval.qa import ask
from src.llm import call_llm_structured
from src.prompts.qa import QA_SYSTEM_PROMPT
from src.retrieval.embedder import embed_texts
from src.retrieval.search import search_similar_context_chunks_by_corpus
from src.schemas import QAResponse

st.set_page_config(
    page_title="RegIntel",
    page_icon="📘",
    layout="wide",
)

st.title("RegIntel")
st.caption("Regulatory change intelligence for FDA CFR content")


def run_query(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    with SessionLocal() as session:
        result = session.execute(text(sql), params or {})
        rows = result.fetchall()
        cols = result.keys()
    return pd.DataFrame(rows, columns=cols)


def load_change_summary() -> pd.DataFrame:
    sql = """
    SELECT
        c.id,
        c.document_short_code,
        c.section_number,
        c.old_date,
        c.new_date,
        c.change_type,
        c.severity,
        c.classification_reason,
        ia.summary,
        ia.recommended_action,
        ia.confidence
    FROM changes c
    LEFT JOIN impact_analyses ia
        ON ia.change_id = c.id
    ORDER BY c.document_short_code, c.section_number, c.old_date, c.new_date
    """
    return run_query(sql)


def load_change_detail(change_id: str) -> pd.DataFrame:
    sql = """
    SELECT
        c.id,
        c.document_short_code,
        c.section_number,
        c.old_date,
        c.new_date,
        c.change_type,
        c.severity,
        c.classification_reason,
        c.raw_diff,
        ia.summary,
        ia.what_changed,
        ia.affected_functions,
        ia.affected_processes,
        ia.recommended_action,
        ia.action_details,
        ia.confidence,
        ia.citations
    FROM changes c
    LEFT JOIN impact_analyses ia
        ON ia.change_id = c.id
    WHERE c.id = :change_id
    """
    return run_query(sql, {"change_id": change_id})


def load_stats() -> pd.DataFrame:
    sql = """
    SELECT
        document_short_code,
        change_type,
        COUNT(*) AS count_rows
    FROM changes
    GROUP BY document_short_code, change_type
    ORDER BY document_short_code, change_type
    """
    return run_query(sql)


def render_changes_tab() -> None:
    st.subheader("Browse changes and impact analyses")

    stats_df = load_stats()
    if not stats_df.empty:
        st.markdown("### Change counts")
        st.dataframe(stats_df, use_container_width=True, hide_index=True)

    df = load_change_summary()

    if df.empty:
        st.info("No change records found.")
        return

    doc_options = ["All"] + sorted(df["document_short_code"].dropna().unique().tolist())
    change_type_options = ["All"] + sorted(df["change_type"].dropna().unique().tolist())
    severity_options = ["All"] + sorted(df["severity"].dropna().unique().tolist())

    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])

    with col1:
        selected_doc = st.selectbox("Document", doc_options, index=0)

    with col2:
        selected_change_type = st.selectbox("Change type", change_type_options, index=0)

    with col3:
        selected_severity = st.selectbox("Severity", severity_options, index=0)

    with col4:
        search_text = st.text_input(
            "Search section / reason / summary",
            placeholder="e.g. complaint, validation, 211.196",
        ).strip()

    filtered = df.copy()

    if selected_doc != "All":
        filtered = filtered[filtered["document_short_code"] == selected_doc]

    if selected_change_type != "All":
        filtered = filtered[filtered["change_type"] == selected_change_type]

    if selected_severity != "All":
        filtered = filtered[filtered["severity"] == selected_severity]

    if search_text:
        mask = (
            filtered["section_number"].fillna("").str.contains(search_text, case=False, na=False)
            | filtered["classification_reason"].fillna("").str.contains(search_text, case=False, na=False)
            | filtered["summary"].fillna("").str.contains(search_text, case=False, na=False)
        )
        filtered = filtered[mask]

    st.markdown(f"### Results ({len(filtered)})")

    display_cols = [
        "id",
        "document_short_code",
        "section_number",
        "old_date",
        "new_date",
        "change_type",
        "severity",
        "recommended_action",
        "confidence",
        "summary",
    ]
    st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)

    change_ids = filtered["id"].astype(str).tolist()
    if not change_ids:
        st.info("No matching changes.")
        return

    selected_change_id = st.selectbox("Select a change to inspect", change_ids)

    detail_df = load_change_detail(selected_change_id)
    if detail_df.empty:
        st.warning("Could not load change details.")
        return

    row = detail_df.iloc[0]

    st.markdown("---")
    st.markdown(f"## {row['document_short_code']} — {row['section_number']}")
    st.write(
        f"**Dates:** {row['old_date']} → {row['new_date']}  \n"
        f"**Type:** {row['change_type']}  \n"
        f"**Severity:** {row['severity']}"
    )

    st.markdown("### Classification reason")
    st.write(row["classification_reason"] or "No classification reason stored.")

    st.markdown("### Raw diff")
    st.code(row["raw_diff"] or "", language="diff")

    st.markdown("### Impact analysis summary")
    st.write(row["summary"] or "No impact analysis summary stored.")

    st.markdown("### What changed")
    st.write(row["what_changed"] or "No structured what_changed field stored.")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("### Recommended action")
        st.write(row["recommended_action"] or "—")
    with col_b:
        st.markdown("### Confidence")
        st.write(row["confidence"] or "—")
    with col_c:
        st.markdown("### Affected functions")
        st.write(row["affected_functions"] or "—")

    st.markdown("### Affected processes")
    st.write(row["affected_processes"] or "—")

    st.markdown("### Action details")
    st.write(row["action_details"] or "No action details stored.")

    st.markdown("### Citations")
    st.json(row["citations"] if row["citations"] is not None else [])


def render_ask_tab() -> None:
    st.subheader("Ask a regulatory question")

    corpus_mode = st.selectbox(
        "Corpus",
        ["us_fda", "eu_gmp", "ich"],
        index=0,
        key="corpus_mode",
    )

    default_questions = {
        "us_fda": "What are the requirements for equipment cleaning and maintenance under 21 CFR 211?",
        "eu_gmp": "What does EU GMP Annex 1 say about contamination control strategy?",
        "ich": "What does ICH Q10 say about pharmaceutical quality systems?",
    }

    if "ask_question" not in st.session_state:
        st.session_state.ask_question = default_questions[corpus_mode]

    if st.session_state.get("last_corpus_mode") != corpus_mode:
        st.session_state.ask_question = default_questions[corpus_mode]
        st.session_state.last_corpus_mode = corpus_mode

    question = st.text_area(
        "Question",
        key="ask_question",
        height=100,
    )

    top_k = st.slider("Top K retrieved sections", min_value=3, max_value=10, value=7)

    if st.button("Ask", type="primary"):
        if not question.strip():
            st.warning("Enter a question first.")
            return

        with st.spinner("Retrieving sections and generating answer..."):
            if corpus_mode == "us_fda":
                with SessionLocal() as session:
                    result = ask(session, question=question.strip(), top_k=top_k)
            else:
                query_embedding = embed_texts([question.strip()])[0]

                with SessionLocal() as session:
                    rows = search_similar_context_chunks_by_corpus(
                        session,
                        query_embedding=query_embedding,
                        corpus=corpus_mode,
                        limit=5,
                    )

                if not rows:
                    result = {
                        "answer": f"No relevant {corpus_mode} context was found for this question.",
                        "citations": [],
                        "confidence": "low",
                        "retrieved_sections": [],
                        "retrieved_guidance": [],
                        "part_filter": [],
                        "retried_for_citations": False,
                    }
                else:
                    context = "\n\n---\n\n".join(
                        f"[Guidance: {r.document_short_code}] {r.heading or f'Chunk {r.chunk_index}'}\n{r.chunk_text}"
                        for r in rows
                    )

                    system_prompt = QA_SYSTEM_PROMPT.format(context=context)

                    response = call_llm_structured(
                        system_prompt=system_prompt,
                        user_prompt=question.strip(),
                        response_model=QAResponse,
                        model="gpt-4o-mini",
                        temperature=0.0,
                    )

                    result = {
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

        st.markdown("### Answer")
        st.write(result["answer"])

        st.markdown("### Confidence")
        st.write(result["confidence"])

        st.markdown("### Corpus")
        st.write(corpus_mode)

        st.markdown("### Part filter used")
        st.write(result.get("part_filter", []))

        st.markdown("### Retried for invalid citations")
        st.write(result.get("retried_for_citations", False))

        st.markdown("### Citations")
        if result["citations"]:
            citations_df = pd.DataFrame(result["citations"])
            st.dataframe(citations_df, use_container_width=True, hide_index=True)
        else:
            st.info("No citations returned.")

        st.markdown("### Retrieved sections")
        retrieved_df = pd.DataFrame(result["retrieved_sections"])
        if not retrieved_df.empty:
            st.dataframe(retrieved_df, use_container_width=True, hide_index=True)
        else:
            st.info("No sections retrieved.")

        st.markdown("### Retrieved guidance")
        guidance_df = pd.DataFrame(result.get("retrieved_guidance", []))
        if not guidance_df.empty:
            st.dataframe(guidance_df, use_container_width=True, hide_index=True)
        else:
            st.info("No guidance chunks retrieved.")


tab_changes, tab_ask = st.tabs(["Changes", "Ask"])

with tab_changes:
    render_changes_tab()

with tab_ask:
    render_ask_tab()