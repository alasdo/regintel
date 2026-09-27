# RegIntel v2 — Vision

Status: draft · Date: 2026-09-27 · Owner: Anas Lasri Doukkali

## Problem and audience

FDA warning letters are the most detailed public record of *why* drug manufacturers fail CGMP. They are published as unstructured HTML, one letter at a time. Questions like "how often is data integrity cited in API letters, and how has that changed since 2019?" or "show me letters where OOS results were invalidated without root cause" take hours of manual reading.

RegIntel v2 is a free, public site that collects CDER drug-manufacturer warning letters, classifies each one into a GMP failure taxonomy with a quoted passage for every label, and makes the cited passages searchable.

- **Primary audience:** QA, QC and regulatory professionals at drug manufacturers, CMOs and API sites; GMP consultants and auditors preparing for inspections.
- **Secondary audience:** hiring managers reviewing this as a portfolio project. It should show data engineering, *measured* AI, and domain insight into pharma manufacturing.

## Goals

1. **Corpus.** Ingest every CDER warning letter to drug manufacturers from FY2019 onward. Tag each letter with a deterministic *letter type* derived from its subject line: CGMP finished dose, API (ICH Q7), compounding (503A/503B), or unapproved/misbranding. Record the close-out status where FDA has published a close-out letter. Collection runs weekly through GitHub Actions.
2. **Classification.** Assign letter-level, multi-label GMP categories (taxonomy below), using a local 7–8B instruct model through Ollama with schema-constrained JSON output. Every label carries at least one verbatim quote from the letter. Unapproved/misbranding content is tagged but not classified. Mixed letters are labelled on their CGMP content only.
3. **Search.** Hybrid retrieval (BM25 + local embeddings, fused with reciprocal rank fusion at the default *k*) over letter passages. Results show the highlighted passage and link to the letter on fda.gov.
4. **Trends.** Category frequency by fiscal year and letter type, set beside the FDA Data Dashboard inspection citations as an independent structured signal.
5. **Evaluation as the core deliverable.** A published, reproducible evaluation with a baseline, a blind held-out test set, and a human-consistency ceiling (protocol below).
6. **An honest public site.** Every page carries a disclaimer: labels are automated and may be wrong, the FDA letter is the authoritative source (linked), and nothing on the site is regulatory advice. Each letter shows its close-out status where FDA has published one.

## Non-goals (v1)

- Generated answers, summaries or chat. Retrieval only.
- Form 483 documents; CBER, CDRH and food letters; non-US regulators.
- Firm risk scores, compliance predictions or rankings of named companies.
- Fine-tuning. Prompting and schema only.
- Legal or regulatory advice (see the disclaimer in goal 6).
- Accounts, authentication, or paid infrastructure of any kind.

## Data sources

| Source | Use | Access |
|---|---|---|
| FDA warning letters (fda.gov listing + letter pages), CDER, FY2019→ | Corpus, labels, search | Public HTML; scraped politely (rate-limited, cached, retried) |
| FDA Data Dashboard, inspection citations (drugs) | Trend cross-check: CFR citation and short description by fiscal year | Public download. These are structured records; the raw 483 documents are not used |
| 21 CFR 210/211, ICH Q7 section numbering | Taxonomy citations and the baseline mapping | Static reference table in the repo |

Raw letter HTML, parsed text and every classification run are kept as versioned files with their source URL, fetch timestamp and content hash. Re-runs never overwrite earlier outputs silently.

## Architecture and zero-cost constraint

Everything runs at **$0/month**:

- **Collection:** a weekly GitHub Actions job (free for public repos) fetches new letters, parses them and commits them. It never calls a model.
- **Classification:** runs on my PC (RTX 4060, 8 GB VRAM) with a quantised 7–8B model in Ollama, at temperature 0 with a fixed seed. The model is chosen on the dev set only. Results are committed with the model, prompt hash and run date. The site shows **"classified up to <date>"**. Newer letters are searchable but marked *not yet classified*.
- **Serving:** a small FastAPI backend and a custom HTML/CSS/JS front end in a Hugging Face Docker Space on free CPU. The design comes from `/design` (DESIGN.md) and is checked with `/ui-review`. No Gradio or Streamlit. Indexes are built offline and shipped with the image. Query embedding uses a small CPU model.
- **No paid APIs, databases or hosting.** Cold starts on the free Space are an accepted trade-off.

## Evaluation protocol

All gold labels are mine, produced **blind**: no model output is seen before labelling is finished.

1. **Labelling guide and baseline mapping first.** Before any labelling, I write `docs/labelling-guide.md`: the category definitions, the boundary rules from the taxonomy table, and worked examples. The CFR-citation → category mapping the baseline uses is frozen in the same commit, before any model output exists. Any change to either after labelling starts is logged in the guide's changelog.
2. **Labelling tool.** An early deliverable: a fast local tool that shows each letter with its observations already split out, a checkbox per category, and a quote field that is checked as verbatim when saved. It never shows model or baseline output. Target: about 4 minutes per letter.
3. **Sample.** 150 letters, drawn with a fixed seed and stratified by fiscal year × letter type. A few unapproved/misbranding letters are included so false positives on non-CGMP text are measured.
4. **Split.** 50 dev letters for prompt and model development, and 100 test letters, split on the same strata. **The test set is evaluated once.** The prompt, model and code commit are frozen and recorded before the run.
5. **Baseline.** A deterministic CFR-citation mapping: extract 21 CFR / FD&C Act / Q7 references from the letter and map them to categories using the table below. Results are reported overall and by letter type; API letters cite fewer CFR sections, so they are likely to be the baseline's weak spot.
6. **Metrics.** Per-category precision, recall and F1 with support and 95% bootstrap CIs, plus micro and macro averages. The headline numbers get a **paired bootstrap** 95% CI: letters are resampled with replacement (10,000 resamples, fixed seed), and model and baseline are scored on the same resample. CIs are reported for macro-F1 (model − baseline) and for model micro-F1. A category with fewer than 5 test positives is reported as *insufficient support* and left out of macro-F1, with a note. Categories are never quietly merged.
7. **Quote verification.** A label counts only if its quote is a verbatim span of the letter after whitespace normalisation. A label that fails is dropped before scoring, and the drop rate is reported.
8. **Self-consistency.** 20 letters (seeded, drawn from dev and test) are re-labelled at least 3 days later without looking at the first pass. I report Cohen's κ per category. A category with κ < 0.6 is flagged *ill-defined* in the eval report and the UI. Test gold is not changed; guide fixes go to the next version.
9. **Search.** About 40 questions, each with known relevant letters, written before retrieval is built. Metrics are recall@5 for hybrid versus BM25-only and embeddings-only, plus citation validity. Fusion parameters are not tuned on this set.

### Success criteria (test set)

| Criterion | Pass if |
|---|---|
| Model vs baseline | macro-F1 (model − baseline) ≥ 0.10; paired bootstrap 95% CI reported |
| Absolute floor | micro-F1 ≥ 0.75; paired bootstrap 95% CI reported |
| Quote validity (labels shown on site) | 100% verbatim |
| Human ceiling | reported: model–gold agreement shown against my self-κ |
| Search recall@5 | hybrid ≥ 0.80, and above both single-method runs |
| Search citation validity | 100%: every highlight is a verbatim span of the linked letter, and the link resolves |

Pass bars are judged on point estimates, with the CIs shown next to them. If a pass bar is not met, the result is reported as-is; bars are not changed after results are seen.

### Lessons from v1 (regintel-legacy)

v1 reported 82% classification accuracy, 97.4% citation validity and recall@5 of 0.72. The 82% came from 11 cases whose gold labels were stored next to the model's output, and it had no baseline. Citation validity only checked that a cited section had been retrieved, and it was measured after a retry. v2 keeps what worked: structured output, citation checking, and iteration notes on failure modes. It fixes how the numbers are measured: blind gold, a held-out test set, a baseline, CIs, and verbatim quote checks.

## Timeline and priorities (one week)

Build order starts with ingestion, the labelling guide with the frozen baseline mapping, and the labelling tool, so labelling can begin by day 2. Protected, never cut: the labelling guide, the labelling tool, 150 blind labels, the baseline, the single test-set evaluation, and deployed search. If the week slips, cut in this order: (1) Data Dashboard trend views, (2) front-end polish beyond `/ui-review` blockers, (3) the weekly Action, replaced by a manual collection script.

**Risks:** labelling 150 letters plus 20 re-labels is the critical path. With the labelling tool at about 4 min per letter, that is roughly 11–12 h, up to about 20 h if long letters run 7 min. Mitigation: time the first 10 letters, and if the pace is over 6 min, fix the tool (observation splitting, quote entry) before continuing, not the guide. Long letters may exceed the context that fits in 8 GB VRAM; the mitigation is to classify per numbered observation and take the union of labels. Warning-letter HTML varies in format across years.

## Draft taxonomy

Letter-level, multi-label. An empty set means no CGMP content. The citation column also defines the baseline mapping, which is frozen together with the labelling guide. A citation that maps to more than one category, such as 211.194(a), maps to all of them.

| # | Category | Definition and boundary rules | Typical citations |
|---|---|---|---|
| 1 | Quality unit oversight | QU lacks authority, procedures or execution: release without adequate review, no oversight of contract manufacturers or labs, missing or inadequate annual product review. Use when the letter faults the QU itself, not just a downstream failure. | 211.22; 211.180(e); Q7 §2 |
| 2 | Data integrity | Records cannot be trusted (ALCOA+): audit trails disabled or unreviewed, shared logins, deleted or trial injections, backdating, falsification, uncontrolled blank forms. Trustworthiness only. Records that are merely incomplete belong in 11. | 211.68(b); 211.194(a); Q7 §5.4, §6.6 |
| 3 | Lab controls and testing | Scientifically unsound specifications, methods or sampling; missing or unvalidated tests; OOS results invalidated without an assignable lab cause; inadequate Phase I lab investigation. | 211.160; 211.165; 211.194; Q7 §11.1–11.4 |
| 4 | Investigations, deviations and CAPA | Deviations, complaints, batch failures or OOS results not investigated thoroughly: no extension to manufacturing, no root cause, no or ineffective CAPA, no review of other affected batches. Can co-occur with 3 for the same OOS. | 211.192; 211.198; 211.100(b); Q7 §15 |
| 5 | Process validation and production controls | Process not validated (PPQ, ongoing verification), inadequate in-process controls, uncontrolled changes (change control), deviating from master instructions during manufacture. | 211.100(a); 211.110; 211.113(a); Q7 §8, §12, §13 |
| 6 | Cleaning and equipment | Unvalidated or inadequate cleaning, cross-contamination risk from shared equipment, equipment design, maintenance, calibration and qualification. | 211.63; 211.65; 211.67; 211.68(a); 211.182; Q7 §5.1–5.3, §12.7 |
| 7 | Aseptic processing and sterility assurance | Poor aseptic technique, inadequate media fills, unqualified sterilisation, poor smoke studies or airflow, weak sterility testing, insanitary conditions affecting sterile compounding. | 211.113(b); 211.42(c)(10); 211.167(a); FD&C 501(a)(2)(A) |
| 8 | Facilities, utilities and environmental monitoring | Building design, cleanliness and pest control; HVAC; water systems; EM programmes (non-aseptic, or site-wide). Use 7 when the EM failure is specific to an aseptic operation. | 211.42; 211.46; 211.48; 211.56; 211.58; Q7 §4; FD&C 501(a)(2)(A) |
| 9 | Supplier and component control | Components not tested or identity-verified (including DEG/EG testing of high-risk components), reliance on supplier CoAs without qualification, containers and closures, material handling. | 211.80; 211.82; 211.84; 211.87; Q7 §7 |
| 10 | Stability and expiry | No or inadequate stability programme, unsupported expiry or retest dates, stability failures not acted on. | 211.166; 211.137; Q7 §11.5–11.6 |
| 11 | Batch records and documentation | Master or batch records missing, incomplete or not reviewed; inadequate written procedures; record retention. No suggestion that the records are untrustworthy (otherwise use 2). | 211.186; 211.188; 211.184; 211.180(a)–(d); Q7 §6 |
| 12 | Packaging and labelling control | Label issuance, reconciliation, line clearance and mix-ups; packaging operations. Excludes misbranding *claims*, which are tagged as a letter type and not classified. | 211.122–211.134; Q7 §9 |
| 13 | Personnel and training | Staff not trained or qualified for their duties; gowning and hygiene practices (use 7 when the practice is aseptic-specific). | 211.25; 211.28; Q7 §3 |
