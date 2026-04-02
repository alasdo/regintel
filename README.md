# RegIntel

RegIntel is a regulatory intelligence prototype for FDA CFR content. It ingests eCFR regulation text, detects changes across versions, classifies those changes, generates impact analyses, stores embeddings for semantic retrieval, and supports a Q&A workflow over the current corpus.

## What the system does

The system currently supports:

- ingesting selected CFR parts from the eCFR API
- parsing regulation XML into structured sections
- storing historical versions of regulation text in PostgreSQL
- detecting changes between two versions of a CFR part
- classifying changes as substantive, editorial, or structural
- generating structured impact analyses for substantive changes
- embedding regulation sections and context documents with OpenAI embeddings
- semantic retrieval over the current regulatory corpus
- a Streamlit UI with:
  - **Changes** tab: browse changes and impact analyses
  - **Ask** tab: ask regulatory questions and get cited answers

## Current corpus

The current prototype corpus includes:

- 21 CFR Part 11
- 21 CFR Part 210
- 21 CFR Part 211
- 21 CFR Part 820
- Federal Register preamble context for the Part 820 QMSR transition

## Stack

- Python
- uv
- PostgreSQL
- pgvector
- SQLAlchemy
- Alembic
- Streamlit
- OpenAI API
- Pydantic

## Project structure

Important files and directories include:

- `src/ingestion/` — eCFR client and parser
- `src/db/` — SQLAlchemy models and DB session
- `src/retrieval/` — embeddings, retrieval, and Q&A pipeline
- `src/analysis/` — classifier and impact analysis logic
- `src/prompts/` — LLM prompts
- `scripts/` — runnable scripts for loading, embedding, diffing, classifying, and asking questions
- `streamlit_app.py` — Streamlit UI entrypoint

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Set environment variables

Create a `.env` file in the repo root with at least:

```
DATABASE_URL=postgresql+psycopg://regintel:regintel@localhost:5432/regintel
OPENAI_API_KEY=your_key_here
```

### 3. Start PostgreSQL

If using Docker Compose:

```bash
docker compose up -d
```

### 4. Apply migrations

```bash
uv run alembic upgrade head
```

## Running the ingestion and analysis pipeline

### Load a CFR part

```bash
uv run python -m scripts.load_ecfr_part --title 21 --part 211 --date 2026-03-30
```

### Detect changes

```bash
uv run python -m scripts.detect_changes --title 21 --part 211 --from-date 2020-01-01 --to-date 2026-03-30
```

### Classify changes

```bash
uv run python -m scripts.classify_changes
```

### Generate impact analyses

```bash
uv run python -m scripts.analyze_impacts
```

### Embed sections

```bash
uv run python -m scripts.embed_sections
```

### Ask a question from the CLI

```bash
uv run python -m scripts.ask "What are the requirements for equipment cleaning and maintenance under 21 CFR 211?"
```

## Running the Streamlit UI

Start the app with:

```bash
uv run streamlit run streamlit_app.py
```

Then open the local URL shown in the terminal.

### Streamlit tabs

#### Changes

Use this tab to:

- browse detected changes
- filter by document, change type, and severity
- inspect raw diffs
- review stored impact analyses

#### Ask

Use this tab to:

- enter a natural-language regulatory question
- retrieve relevant sections
- view the cited answer
- inspect retrieved sections and confidence

### Q&A behavior

The Q&A pipeline includes:

- semantic retrieval over embedded regulation sections
- part-aware retrieval filtering
- current-version-only retrieval by default
- reserved-section filtering
- structured LLM output
- citation validation
- one retry if the model cites a section that was not retrieved

## Evaluation files

The project includes seed evaluation files such as:

- `eval/test_cases/classification_labels.jsonl`
- `eval/test_cases/qa_golden.jsonl`
- `eval/impact_prompt_iteration_notes.md`
- `eval/qa_iteration_notes.md`

These are intended to support iterative evaluation of:

- change classification
- impact analysis quality
- Q&A grounding and retrieval quality

## Known limitations

- The corpus is still limited and is not a full GMP or legal reference library.
- Q&A quality depends on retrieval quality and current corpus coverage.
- Transition rules such as Part 820 may require Federal Register context to avoid naive interpretation of removed sections.
- The system is a regulatory intelligence aid, not legal advice.
- Some complex questions may require broader contextual materials that are not yet ingested.

## Suggested next improvements

- add historical vs current retrieval modes in the UI
- add automated evaluation scripts for Q&A and impact analyses
- add richer context ingestion for major rulemakings
- add export/download options from Streamlit
- add authentication if deployed internally
- improve retrieval reranking and keyword-aware filtering
## Architecture

```mermaid
flowchart TD
    A[eCFR API / Federal Register] --> B[XML / text ingestion]
    B --> C[Parser / chunker]
    C --> D[PostgreSQL]

    D --> E[Regulation parts / sections]
    D --> F[Changes]
    D --> G[Impact analyses]
    D --> H[Context chunks]

    E --> I[Embeddings]
    H --> I
    I --> J[pgvector similarity search]

    E --> K[Version comparison]
    K --> F

    F --> L[LLM change classification]
    L --> F

    F --> M[LLM impact analysis]
    J --> M
    H --> M
    M --> G

    N[User question] --> O[Question embedding]
    O --> J
    J --> P[Retrieved sections]
    P --> Q[LLM Q&A]
    Q --> R[Citation validation]
    R --> S[CLI / Streamlit UI]

    classDef rule fill:#eef,stroke:#447;
    classDef llm fill:#efe,stroke:#474;
    classDef store fill:#fee,stroke:#744;

    class B,C,K rule;
    class L,M,Q llm;
    class D,E,F,G,H,I,J store;