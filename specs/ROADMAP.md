# RegIntel v2 roadmap (8 days: Day 0 plus 7 build days)

Source: `docs/vision.md` and `docs/decisions/0001-architecture.md`. Each slice becomes a spec in `specs/` (`/spec` → `/implement`). A milestone is done when every exit criterion is checked and `make check` passes on its merged branch.

**Protected (never cut):**
- labelling guide
- labelling tool
- 150 blind labels
- baseline
- single test evaluation
- deployed search

**Blindness rule (per letter):** model and baseline outputs on the 150 sample letters stay hidden until all 150 are labelled. The sample guard in `classify` and `baseline` enforces this. From the walking skeleton onwards, classifying letters outside the sample is allowed. The residual priming risk is recorded as a limitation in `docs/vision.md`.

## Day 0 (Phase 0, 2026-09-27): Vision, architecture, roadmap

**Demo:** one PR containing `docs/vision.md`, `docs/decisions/0001-architecture.md` and this roadmap.

**Exit criteria**
- [x] The three vision amendments from 0001 and the per-letter blindness limitation are applied to `docs/vision.md`.
- [ ] The PR "Phase 0: vision, architecture, roadmap" is open, and `make check` passes on its branch.

**Slices**
1. Vision
2. Architecture decision record 0001
3. Roadmap

## Day 1: Collector and parser

**Demo:** `regintel collect` pulls the live-listing (2021→) drug letters and their HTML into the HF Dataset. `regintel parse <letter_id>` prints the metadata and numbered observations for a 2021 letter and a 2025 letter.

**Exit criteria**
- [ ] `raw/manifest.jsonl` on the Dataset has one line per letter, with `sha256`, URL and `retrieved_at`. A second run adds 0 lines.
- [ ] Parser golden tests pass on ≥ 10 real fixtures (at least one per FY 2021–2026, at least one per letter type).
- [ ] The parse report over the full corpus shows `unknown` letter types = 0 (or each one is listed and fixed) and states the fallback-segmentation rate.
- [ ] Sample (150), dev/test split and the relabel list (20, test only) are committed with hashes, drawn with a fixed seed and stratified FY × type.
- [ ] Owner deliverable: `docs/labelling-guide.md` (including the label-scope rule: cited violations only, remediation sections excluded) and `reference/cfr_map.csv` are committed together, before any model output exists.
- [ ] The probe Action, dispatched manually, fetches one fda.gov letter page and logs the HTTP status and the body sha256. If it is blocked, the fallback to manual collection is recorded before Day 5.

**Slices**
1. Listing scraper and polite fetcher (rate limit, retry, cache)
2. Manifest and HF Dataset store
3. Quote normalisation, canonical text, observation segmentation and remediation tagging
4. Letter metadata and subject-line letter type (the rule table already exists as `regintel.letter_type`, from spec 0001)
5. Stratified sample and frozen split files
6. Bot-block probe Action (manual dispatch)

## Day 2: Labelling tool, then labelling

**Demo:** label a real letter in the Streamlit tool. A non-verbatim quote is refused, and the saved JSONL line is shown.

**Exit criteria**
- [ ] The import-boundary test proves that `label/` cannot reach predictions or baseline output.
- [ ] Saving is refused on a failed quote (test). Re-label mode hides first-pass labels and enforces the ≥ 3-day gap (tests).
- [ ] The first 10 letters are timed. If the median is over 6 min, the tool is fixed before labelling continues (the guide is not the fix).
- [ ] By end of day, ≥ 50 letters are labelled.
- [ ] `evaluation/search/questions.jsonl` has ~40 questions with relevant letter IDs, committed before any retrieval code exists.

**Slices**
1. Label store (JSONL, append-only, verbatim check)
2. Streamlit labelling UI with observation view
3. Re-label mode
4. Blindness import-boundary guard
5. Search question set (owner)

## Day 3: Walking skeleton

**Demo:** the live HF Space answers a query over 20 letters from outside the 150-letter sample, shows highlighted passages linked to fda.gov, and shows labels with quotes, the disclaimer, and "classified up to".

**Exit criteria**
- [ ] All 150 gold labels are committed by end of day.
- [ ] The skeleton classifies only non-sample letters, and a test proves that the sample guard refuses sample IDs for both `classify` and `baseline` while gold holds fewer than 150.
- [ ] `run.json` for the 20-letter run records the model digest, prompt hash, settings, `config_hash`, commit and quote-drop count.
- [ ] Every label shown on the Space has a verified quote (bundle test).
- [ ] The Space cold-starts, pulls the pinned bundle and returns `/api/search` results. The `TestClient` suite passes on a fixture bundle.

**Slices**
1. Per-observation Ollama classifier and quote verification
2. Run record and classify guards (sample and test refusal)
3. Passages, BM25, embeddings and RRF
4. Bundle export and Dataset push
5. FastAPI app, minimal static UI and Space Dockerfile

## Day 4: Backfill and prompt development begins

**Demo:** the Space searches the full corpus. The dev eval report shows model vs baseline per category.

**Exit criteria**
- [ ] The full corpus is parsed, indexed and live. Unclassified letters, including all test letters, are marked *not yet classified*.
- [ ] The baseline runs on dev and the dev report exists (per-category P/R/F1, micro/macro, by letter type, quote-drop rate).
- [ ] Prompt iterations are logged (run ID, change, dev macro-F1, failure notes). No run touches a test letter (guard test).

**Slices**
1. Full-corpus parse and index backfill
2. CFR citation baseline
3. Metrics, bootstrap CIs and the dev report
4. Prompt iteration log and model comparison on dev

## Day 5: Search evaluation, weekly Action, trends

**Demo:** the search eval table (hybrid vs BM25 vs embeddings), a green weekly Action run on GitHub, and the trends page by FY and letter type beside the Dashboard citations.

**Exit criteria**
- [ ] `evaluation/results/search.json` gives recall@5 for all three modes and citation validity, with fusion untuned.
- [ ] A dispatched Action run pushes new raw data (or pushes nothing when nothing is new) and calls no model (CI grep test).
- [ ] Trend aggregation passes the FY boundary tests (30 Sep and 1 Oct).
- [ ] Prompt and model are chosen on dev, and the dev results are committed.

**Slices**
1. Search evaluation harness
2. Weekly collect workflow
3. Data Dashboard ingest
4. FY trend aggregation and trends page

## Day 6: Freeze and the one-time test evaluation

**Demo:** the freeze record, the guard refusing a mismatched config, then the single test run and its report.

**Exit criteria**
- [ ] The 20 test-only re-labels are done before the test run, and κ per category is computed.
- [ ] `docs/decisions/NNNN-test-freeze.md` is committed with `config_hash` (which includes the `normalise` hash), commit and test-split hash. The guard tests prove refusal on mismatch and on a second scoring.
- [ ] `evaluation/results/test/` holds per-category P/R/F1 with CIs, paired bootstrap CIs for Δmacro-F1 and micro-F1, results by letter type, quote-drop rate, and κ with ill-defined flags. Pass bars are reported as-is.
- [ ] The full corpus is classified with the frozen config, and the bundle is republished.

**Slices**
1. Self-consistency re-labels and κ
2. Freeze record and guard
3. Test-split scoring and report
4. Frozen full-corpus classification and bundle

## Day 7: Ship

**Demo:** the public Space and a README whose numbers link to results files.

**Exit criteria**
- [ ] The README-vs-results consistency test passes.
- [ ] `/ui-review` has no blockers. Disclaimer, "classified up to", close-out status and ill-defined flags are visible.
- [ ] Every page's FDA links resolve (link check at eval time; mocked in tests).
- [ ] The handoff note is written.

**Slices**
1. README generated from results
2. Letter page, close-out status and ill-defined flags
3. UI polish to DESIGN.md and `/ui-review` fixes
4. Release: pinned bundle revision and tag

## If the schedule slips

Cut in this order (from the vision):
1. Data Dashboard trend views (Day 5, slices 3–4; the FY trends of labels stay)
2. Front-end polish beyond `/ui-review` blockers (Day 7, slice 3)
3. The weekly Action, replaced by the manual `regintel collect` script (Day 5, slice 2)

The protected items are never cut. If labelling runs long, everything that scores sample letters (the baseline, dev prompt development, and everything after them) moves right. The skeleton and non-sample classification do not wait. The blindness rule is not relaxed.
