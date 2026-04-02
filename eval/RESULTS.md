# Results

## Corpus size

Document the current corpus here.

Suggested items:
- number of parts ingested
- number of section rows
- number of context documents
- number of context chunks

## Change detection

Document:
- number of changes detected
- distribution by document
- distribution by change type
- severity distribution

## Classification evaluation

Paste the output summary from `eval/run_classification_eval.py` here.

## Q&A evaluation

Paste the output summary from `eval/run_qa_eval.py` here.

## Impact analysis review

Summarise average rubric scores from `eval/impact_review.md`.

## Known limitations

Examples:
- current corpus is still limited
- transition-rule interpretation remains hard
- retrieval quality is good but not fully optimised
- impact analysis still needs richer contextual sources in some cases

## Failure modes observed

Examples:
- removed codified sections sometimes overstated as removed obligations
- semantically related but wrong-part retrieval before part filtering
- invalid citations before retry logic

## Iterations that improved the system

Examples:
- part-aware retrieval filtering
- current-version-only retrieval
- reserved-section filtering
- Federal Register preamble ingestion
- stricter Pydantic schemas