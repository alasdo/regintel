# RESULTS

## System overview

RegIntel is a regulatory intelligence system that ingests structured regulatory and guidance documents, stores them in a searchable database, detects changes between regulatory versions, classifies those changes, generates impact analyses, and answers natural-language questions with retrieved, cited context.

## Corpus

### US FDA
- 21 CFR Part 11
- 21 CFR Part 210
- 21 CFR Part 211
- 21 CFR Part 820
- Federal Register preamble for the Part 820 revision
- FDA Data Integrity guidance
- FDA Process Validation guidance
- FDA Aseptic Processing guidance
- FDA Quality Systems guidance

### EU GMP
- EU GMP Annex 1
- EU GMP Annex 11
- EU GMP Chapter 4

### ICH
- ICH Q10
- ICH Q9(R1)

### Corpus counts
- **Total regulation sections:** 303
- **Total context documents:** 10
- **Total context chunks:** 827

## Change detection

- **Total changes detected:** 43

### Changes by document
- **21CFR211:** 7
- **21CFR820:** 36

### Distribution by change type
- **Substantive:** 37
- **Editorial:** 4
- **Structural:** 2

### Distribution by severity
- **High:** 35
- **Medium:** 2
- **Low:** 6

## Classification accuracy

Classification evaluation results from `eval/run_classification_eval.py`:

- **Labelled cases:** 11
- **Exact type + severity accuracy:** 81.82%

### Accuracy by expected change type
- **Substantive:** 6/7 (85.71%)
- **Editorial:** 3/3 (100.00%)
- **Structural:** 1/1 (100.00%)

### Severity accuracy for substantive changes
- **High:** 3/3 (100.00%)
- **Medium:** 2/4 (50.00%)
- **Low:** 0/0 (0.00%)

### Confusion summary
- **Substantive →** substantive: 6, editorial: 1, structural: 0
- **Editorial →** substantive: 0, editorial: 3, structural: 0
- **Structural →** substantive: 0, editorial: 0, structural: 1

## Q&A evaluation

Q&A evaluation results from `eval/run_qa_eval.py`:

- **Test cases:** 31
- **Overall retrieval recall@5:** 0.720
- **Overall retrieval recall@7:** 0.731
- **Citation validity:** 0.974
- **Out-of-scope handling:** 1/1 correct

### Per-corpus breakdown
- **EU GMP:** 8 cases, recall@5 = 0.688, recall@7 = 0.688, citation validity = 1.000
- **ICH:** 6 cases, recall@5 = 0.833, recall@7 = 0.833, citation validity = 1.000
- **US FDA:** 17 cases, recall@5 = 0.696, recall@7 = 0.716, citation validity = 0.958

### Interpretation
These results suggest that citation grounding is strong across all corpora, with especially strong citation validity in the EU GMP and ICH corpora. Retrieval remains the main area for improvement, particularly in the FDA and EU GMP corpora, where recall@5 and recall@7 indicate that relevant sources are not always retrieved in the top results.

## Impact analysis quality

Summarise results from `eval/impact_review.md`.

## Known limitations and failure modes

- Part 820 removed sections initially overstated as removed obligations
- out-of-scope handling still needs broader evaluation beyond the current limited sample
- retrieval gaps remain for some broad or cross-framework queries
- some guidance and ICH chunking required cleanup to avoid TOC-style noise
- compare-mode is not yet implemented

## Prompt iteration history

### Change classification prompt
Improved conservative behavior and reduced overuse of “structural” for meaningful removals.

### Impact analysis prompt
Added removed-section caveat and explicit transition-context logic to reduce false “requirement eliminated” claims.

### Q&A prompt and retrieval
Added:
- part-aware routing
- current-version-only CFR retrieval
- citation retry
- reserved-section filtering
- corpus-aware routing

## Portfolio significance

The project demonstrates:
- hybrid rule-based + LLM system design
- structured regulatory ingestion
- retrieval-augmented generation across multiple corpora
- quantitative evaluation
- iterative prompt and retrieval improvement based on observed failures