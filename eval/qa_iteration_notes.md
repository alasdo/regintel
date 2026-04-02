# Q&A Iteration Notes

## Scope of the Q&A pipeline
The Q&A pipeline was built to answer natural-language questions over the regulatory corpus using:
- semantic retrieval over embedded sections
- structured LLM output
- inline section citations
- citation validation against retrieved context

The corpus used for Q&A v1 includes:
- 21 CFR Part 11
- 21 CFR Part 210
- 21 CFR Part 211
- 21 CFR Part 820
- Federal Register preamble context for the Part 820 QMSR revision

---

## Initial Q&A pipeline behavior
The first version of the Q&A pipeline worked end to end, but showed three key issues:

1. **Cross-part retrieval noise**
   - Questions about Part 211 sometimes retrieved Part 820 or Part 11 sections.
   - Example: a 211 equipment-cleaning question retrieved 820 equipment-related sections.

2. **Invalid citations**
   - The model sometimes cited relevant sections that were not in the retrieved context.
   - Example: the equipment-cleaning answer cited Section 211.180 even though it had not been retrieved.

3. **Historical leakage into current Q&A**
   - Questions about current Part 820 sometimes retrieved historical sections from 2020 rather than the current 2026 QMSR snapshot.
   - Example: complaint-file questions initially retrieved 820.198 from the older version instead of answering from the current framework.

---

## Iteration 1: Part-aware retrieval filtering
### Change made
Added question parsing in `ask()` to infer which CFR parts should be searched.

Rules:
- if question explicitly mentions Part 11 or 21 CFR 11 → search `[11]`
- if question explicitly mentions Part 210 or 21 CFR 210 → search `[210]`
- if question explicitly mentions Part 211 or 21 CFR 211 → search `[210, 211]`
- if question explicitly mentions Part 820 or 21 CFR 820 → search `[820]`
- otherwise default to `[11, 210, 211, 820]`

### Observed improvement
Retrieval became much cleaner:
- Part 211 questions primarily returned 210/211 sections
- Part 11 questions returned only Part 11 sections
- Part 820 questions returned only Part 820 sections

This noticeably improved relevance and reduced noisy cross-part hits.

---

## Iteration 2: Retry on invalid citations
### Change made
Added citation validation plus a single retry.

Workflow:
1. generate answer and citations
2. check whether all cited section numbers are present in retrieved context
3. if any citation is invalid, retry once with an explicit instruction:
   - cite only from the retrieved section numbers

### Observed improvement
This fixed the main citation hallucination issue.

Example:
- the 211 equipment-cleaning answer initially cited 211.180 without retrieval support
- after retry logic, the final answer cited only retrieved sections and all citations were valid

This made the Q&A output more reliable without requiring a major redesign.

---

## Iteration 3: Current-version-only retrieval
### Problem
Current Q&A about Part 820 was answering from historical sections that no longer exist in the current codified text.

Example:
- “What does 21 CFR 820 say about complaint files?” initially retrieved 820.198 from 2020

### Change made
Added a `search_similar_sections_current_only(...)` retrieval mode.

This mode:
- finds the most recent `version_date` for each selected part
- searches only `regulation_sections` from those latest part snapshots

### Observed improvement
Questions about current regulations now answer from the current corpus snapshot.

Example:
- the complaint-files question switched from old `820.198` to current `820.35`

This resolved the main historical leakage problem in user-facing Q&A.

---

## Iteration 4: Reserved-section filtering
### Problem
Current Part 820 retrieval still returned noisy `[Reserved]` sections.

Examples:
- 820.5 `[Reserved]`
- 820.40 `[Reserved]`
- 820.20 - 820.30 `[Reserved]`

### Change made
Added filtering in `search_similar_sections_current_only(...)` to exclude reserved sections by title/full text.

### Observed improvement
Part 820 retrieval became cleaner and more useful.

Example:
- complaint-files retrieval no longer surfaced reserved sections
- top retrieved sections were now real current sections such as 820.35, 820.7, 820.10, and 820.1

---

## Quality observations after iteration
### Strong areas
The Q&A system performs well on:
- straightforward factual questions
- section-specific questions
- multi-section questions in Part 211
- Part 11 questions on signatures and audit trails
- out-of-scope trick questions where the answer should decline

Examples that worked well:
- equipment cleaning and maintenance
- batch production records
- laboratory controls and testing
- personnel qualifications and training
- water systems used in drug manufacturing
- Part 11 signature/record linking
- EU GMP trick question

### Remaining limitations
1. **Semantic retrieval still has moderate similarity scores**
   - strong results often fall in the ~0.60 to ~0.75 range
   - retrieval is good, but not yet highly tuned

2. **Some answers remain slightly broad**
   - for complex topics, the model sometimes summarizes generally rather than being maximally section-specific

3. **Current vs historical semantics still matter**
   - the current-only mode is right for most user-facing Q&A
   - but historical or comparison questions will eventually need a dedicated historical retrieval mode

---

## Final state of Q&A v1
The Q&A pipeline now includes:
- semantic retrieval over the regulatory corpus
- structured JSON answers
- inline section citations
- citation validation
- retry on invalid citations
- part-aware retrieval filtering
- current-version-only retrieval mode
- reserved-section filtering

This is sufficient to consider Q&A v1 complete.

---

## Recommended future improvements
1. Add explicit historical retrieval mode for questions like:
   - “What did Part 820 previously require?”
   - “How did the complaint-file requirements change?”

2. Add reranking:
   - keyword overlap
   - section-number boosting
   - metadata-aware reranking

3. Add answer evaluation script against `qa_golden.jsonl`

4. Add support for showing retrieved context snippets directly in the CLI or UI

5. Expand corpus further if broader regulatory Q&A is needed

---

## Milestone conclusion
The Q&A pipeline reached a usable v1 state after iterative improvements to retrieval scoping, citation validation, and current-snapshot handling. The most important gains came from:
- restricting retrieval by explicitly mentioned CFR part
- retrying invalid citations once
- searching only the latest part snapshot for current regulatory questions
- excluding reserved sections from current retrieval

These changes substantially improved answer grounding and practical usefulness.