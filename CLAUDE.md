# regintel

rigor: standard   <!-- or: regulated (see global CLAUDE.md) -->

## Overview

RegIntel v2 is a free, public tool over FDA (CDER) warning letters to drug manufacturers, FY2019 onward. A weekly GitHub Action collects new letters. A local 7–8B model (Ollama) run on the owner's PC classifies each letter into 13 GMP failure categories, with a verbatim quote per label. A FastAPI + HTML/CSS/JS site on a free Hugging Face Docker Space serves hybrid search and trends; FDA Data Dashboard inspection citations provide a second, structured trend source. Scope, taxonomy and the evaluation protocol are in `docs/vision.md`.

## Commands

| Task | Command |
|---|---|
| Install / sync deps | `make setup` |
| Format | `make fmt` |
| Lint + types + tests (definition of done) | `make check` |
| Tests only | `make test` or `uv run pytest tests/path -k name` |
| Run | not defined yet (no app); add when the first entry point lands |

## Layout

- `src/regintel/`: package code
- `tests/`: pytest suite; fixtures in `tests/fixtures/`
- `specs/`: feature specs (`/spec` creates, `/implement` consumes)
- `docs/vision.md`: scope, goals, taxonomy, evaluation protocol and pass bars
- `docs/labelling-guide.md`: category definitions, boundary rules, examples, changelog (written before labelling)
- `docs/decisions/`: decision records for choices that aren't obvious from the code

## Conventions

- UI work follows DESIGN.md.
- Front end is custom HTML/CSS/JS served by FastAPI. No Gradio or Streamlit.
- Zero cost: no paid APIs, databases or hosting. Embeddings and classification run locally.
- GitHub Actions only collects and commits letters; it never calls a model.
- Model runs use temperature 0 and a fixed seed, and record model name, prompt hash and run date with their outputs.

## Domain rules

- In scope: CDER warning letters to drug manufacturers (CGMP finished dose, API/ICH Q7, compounding 503A/503B). Unapproved-drug and misbranding letters are ingested, tagged by letter type and searchable, but not classified. Form 483 documents are out of scope.
- Letter type is set deterministically from the letter's subject line, not by the model.
- Labels are letter-level and multi-label. Every label needs a quote that is a verbatim span of the letter (after whitespace normalisation); a label whose quote fails is dropped and never shown.
- Category boundary rules (e.g. OOS split between lab controls and investigations; data integrity vs documentation) live in `docs/labelling-guide.md`, not in decision records.
- The labelling guide and the baseline's CFR-citation → category mapping are frozen together before any model output exists; later changes go in the guide's changelog.
- Gold labels are made blind: no model or baseline output is shown before labelling is finished.
- The 100-letter test set is evaluated once, with the prompt, model and commit frozen first. Never use it for prompt or model development, and never edit test gold after results are seen.
- Pass bars in `docs/vision.md` are not changed after results are seen; a missed bar is reported as-is.
- Trends use FDA fiscal years (1 Oct – 30 Sep).
- Raw letters and every classification run are versioned with source URL, fetch timestamp and content hash; nothing is overwritten silently.
- The public site shows a disclaimer (automated labels may be wrong, FDA letter is authoritative and linked, not regulatory advice), "classified up to <date>", and close-out status where FDA has published one.

## Gotchas

- Warning-letter HTML on fda.gov varies in format across years; parsers need fixtures from several years.
- API letters often cite ICH Q7 sections or FD&C 501(a)(2)(B) instead of 21 CFR, so the CFR baseline is weak there; always report metrics by letter type.
- 8 GB VRAM limits the context window; long letters may need per-observation classification with a union of labels.
- FDA Data Dashboard citations are structured records derived from inspections; they are not the raw 483 documents.
- The free Hugging Face CPU Space sleeps when idle; expect cold starts.
