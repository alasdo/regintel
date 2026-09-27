# RegIntel labelling guide

Version 1.0 · 2026-09-27 · Owner: Anas Lasri Doukkali
Status: **draft for the pilot**. Frozen as v1.1, together with `reference/cfr_map.csv`, after the pilot ([section 7](#7-pilot-and-freeze)). The labelling tool records this file's sha256 with every label (`guide_sha`). Every change goes in the [changelog](#changelog).

---

## Quick reference (the labelling screen)

| # | Category | Tick when the cited violation shows… |
|---|---|---|
| 1 | Quality unit oversight | the **QU itself** failed: its procedures, release decisions, contractor oversight, or annual product review |
| 2 | Data integrity | records or data that **cannot be trusted**: deleted, altered, backdated, unaudited, shared logins |
| 3 | Lab controls and testing | lab tests, specs, methods or sampling are **missing, unsound or unvalidated**, or an OOS was invalidated without a lab cause |
| 4 | Investigations, deviations and CAPA | a failure, deviation, complaint or OOS was **not properly investigated** (root cause, scope, CAPA, other batches) |
| 5 | Process validation and production controls | the **manufacturing process** is not validated or controlled: PV, in-process controls, change control, reprocessing |
| 6 | Cleaning and equipment | **equipment** cleaning, design, maintenance, calibration or qualification; cross-contamination from shared equipment |
| 7 | Aseptic processing and sterility assurance | anything that threatens **sterility**: aseptic practice, media fills, sterilisation, classified areas, sterility testing |
| 8 | Facilities, utilities and EM | **building**, pests, HVAC, water and utilities, EM outside classified sterile areas |
| 9 | Supplier and component control | **incoming materials** not tested or identity-checked (incl. DEG/EG), CoA reliance, containers and closures, storage |
| 10 | Stability and expiry | **stability programme** missing or inadequate, expiry or retest dates unsupported, stability failures not acted on |
| 11 | Batch records and documentation | records **missing, incomplete or not reviewed**; document control; retention, with no doubt about their truth |
| 12 | Packaging and labelling control | **label and packaging operations**: issuance, reconciliation, line clearance, mix-ups |
| 13 | Personnel and training | staff **not trained or qualified**; hygiene and clothing outside sterile operations |

Five rules that settle most doubts:

1. **Violations only.** Labels come from the cited violations (observation spans), never from remediation requests, response assessments or "repeat observation" summaries.
2. **Subject, not paperwork.** A missing or unfollowed procedure is labelled by what it governs; 11 is for the document system itself.
3. **OOS.** Invalidating it or a weak lab phase → **3**. A shallow investigation (no root cause, no manufacturing phase, no CAPA, no other batches) → **4**. Both if both are faulted.
4. **Trust versus completeness.** Could the records be false, altered or selectively kept? Then **2**. Just missing or incomplete? Then **11**.
5. **Sterile context.** Conditions in classified (ISO 5–8) areas serving sterile operations → **7**. Everywhere else → **8**.

---

## 1. Purpose and unit

- **Unit:** one set of labels per letter. Labels are letter-level and multi-label: the union of everything the letter's violations support. An empty set is valid.
- **Source of labels:** only the **cited CGMP violations**, meaning the observation spans the tool shows in normal (not greyed) text. The following do **not** create labels on their own:
  - FDA's standard remediation sections and requests, e.g. the data-integrity remediation section ("Data Integrity Remediation"), recommendations to hire a CGMP consultant, and "In response to this letter, provide…" lists. The tool greys these out.
  - FDA's assessment of the firm's response ("Your response is inadequate because…"). It criticises the response, not the operation.
  - "Repeat observations" and "ineffective management oversight" summary paragraphs (see [edge cases](#repeat-observations)).
  - Statutory boilerplate: "adulterated within the meaning of section 501(a)(2)(B)", "prepared, packed, or held under insanitary conditions…".
- **Not labelled:** unapproved-drug and misbranding content. A letter of that type only gets no labels. **Mixed letters** are labelled on their CGMP violations only: a label claim, a missing NDA or an inadequate direction for use never creates a label, not even 12.
- **What a label asserts:** "The letter says this firm failed in this category." It is not a judgement of whether FDA was right, and not an inference about root causes FDA did not state.

## 2. Procedure per letter

Target: about 4 minutes per letter.

1. **Skim the header** (subject, letter type, facility description) for context. It never supplies a label or a quote.
2. **Read each observation in turn.** For each one, ask which categories its *described failure* falls in. Use the quick-reference table and, if needed, the boundary rules below. A single observation often supports 2–3 categories.
3. **Tick every category that applies** across all observations. Each category is ticked once per letter, however many observations support it.
4. **Paste one quote per ticked category.** Use the **shortest verbatim span** that on its own shows a reader why the category applies:
   - Copy it from the tool's canonical text inside an observation span. The tool normalises it the same way as the letter text (NFKC; curly quotes folded to `'`/`"`; all dash and hyphen variants folded to `-`; whitespace collapsed to single spaces; see `docs/decisions/0001-architecture.md`, *Parsing*). The tool refuses a quote that is not an exact substring inside an observation.
   - Prefer the sentence or clause that names the failure ("Your firm failed to validate the cleaning procedures for…") or the concrete fact ("the audit trail was disabled"), whichever is shorter and still self-explanatory.
   - A citation alone ("21 CFR 211.192") is never an adequate quote. Neither is a fragment that needs the surrounding text to make sense.
   - If several observations support the category, pick the clearest one.
5. **Set the unsure flag** where it applies (below), then save.

### Rule for doubt

- **Tick** when the violation text *states or directly describes* a failure of that category's kind, and you can quote a span that a second QA reviewer would accept as showing it.
- **Don't tick** when the category is only:
  - implied by the CFR or Q7 number (the baseline does that, gold does not);
  - a plausible root cause FDA did not state (e.g. "they probably lacked training");
  - mentioned in remediation text, a response assessment or boilerplate;
  - a consequence of another failure that the letter does not itself fault (e.g. a batch was released after a failed investigation, but the letter doesn't criticise the release decision → no 1).
- **Still 50/50 after the boundary rules?** Follow the letter's own framing: its heading sentence ("Your firm failed to…") and the provisions it cites decide which category the failure belongs to. If the framing doesn't settle it, don't tick, and set the unsure flag.
- **Unsure flag (optional, per category).** Mark a category *unsure* whenever you hesitated, whether you ticked it or not. The flag **never changes the label**: scoring uses the ticks only. It is used afterwards to spot ill-defined boundaries (together with the self-consistency κ) and to feed the changelog.

---

## 3. Categories

Each entry has the definition (the line to read at the screen), then includes and excludes, boundary rules, typical citations, and examples. **All examples are paraphrased composites written for this guide, not quotes from the FY2019+ corpus.** Citations below are indicative. The baseline mapping is `reference/cfr_map.csv` (see [section 6](#6-baseline-mapping-referencecfr_mapcsv)).

### 1 · Quality unit oversight

**The quality unit itself lacks authority, procedures or execution, and the letter faults the QU, not only a downstream failure.**

- **Includes:** QU responsibilities or procedures not established or not followed; QU not independent. Release or approval of batches without adequate review, or despite failing or unresolved data. No oversight of contract manufacturers or contract testing labs (the letter is to the product owner). Annual product review missing or inadequate. Responsible officials not informed. Internal audits (API).
- **Excludes:** failures where the QU is not named or faulted (label the subject only). The CMO's or contract lab's *own* failures when the letter is addressed to them (label the subject). "Repeat observation" summaries. Supplier qualification for components (→ 9).
- **Boundaries:**
  - vs **4:** "Deviations were not investigated" → 4 only. "Your QU failed to ensure that deviations were investigated" → 1 + 4.
  - vs **11:** incomplete batch records → 11. The QU released batches without reviewing them → 1 (add 11 only if the records are also faulted as incomplete).
  - vs **9:** a component supplier's CoA relied on without qualification → 9. A contract manufacturer or contract lab not overseen → 1.
- **Typical citations:** 211.22(a)–(d); 211.180(e), (f); Q7 2.1, 2.2, 2.4, 2.5, 16.
- **Examples:**
  - ✔ *The quality unit released three lots of tablets without reviewing the laboratory results, one of which showed a failing assay.* → 1 (plus 3 or 4 only if the letter also faults the testing or the investigation)
  - ✔ *The firm had not performed any annual product review for its marketed products for the past two years.* → 1
  - ✘ *A dissolution failure on lot 123 was never investigated.* → 4, not 1: the QU is not faulted.

### 2 · Data integrity

**Records or data cannot be trusted to be complete, original and accurate (ALCOA+). It is about trustworthiness only.**

- **Includes:** audit trails disabled, not reviewed, or showing deletions. Shared or generic logins; analysts with administrator rights who can delete or alter data. Deleted, overwritten or unreported results; trial, "test" or "prep" injections; orphan data. Backdating; recording before or after the fact; copied or fabricated entries; results transcribed from scrap paper that was then discarded. Uncontrolled blank or loose forms. Data loss from missing backup (211.68(b)). Shared, lent or misused electronic signatures and passwords. Discrepancies between records and what investigators saw that suggest falsification.
- **Excludes:** records that are merely missing or incomplete (→ 11). Computerised-system validation or qualification without a trust problem (→ 6). FDA's data-integrity remediation request section (no label).
- **Boundaries:**
  - vs **11 (vision rule):** ask "could these records be false, altered or selectively kept?" Yes → 2. "They are just absent or lack required entries" → 11. Data that was *generated and then not retained or deleted* → 2. A required field that was *never recorded* → 11.
  - vs **6:** software or instrument not validated or qualified → 6. Access control, audit trail, backup, or who can change data → 2 (owner decision, v1.0).
  - vs **3:** retesting until a pass is obtained → 3 (OOS invalidation). Add 2 only if failing results were hidden, deleted, run as trial injections or not reported.
- **Typical citations:** 211.68(b); 211.194(a); 21 CFR Part 11 (e.g. 11.10, 11.70, 11.300); Q7 5.4, 6.6.
- **Examples:**
  - ✔ *Analysts had administrator privileges on the chromatography software, and the audit trail function was disabled.* → 2
  - ✔ *Batch record entries for several steps were signed as completed on dates before the steps were performed.* → 2
  - ✘ *Batch records did not include the actual weights of components added.* → 11: incomplete, with no suggestion of falsification.

### 3 · Lab controls and testing

**Lab tests, specifications, methods or sampling are missing, scientifically unsound or unvalidated; or OOS results were invalidated without an assignable lab cause.**

- **Includes:** finished product or API not tested against all specifications before release. Specifications or sampling plans not scientifically sound. Analytical methods not validated or verified (incl. compendial suitability). Reference standards; reserve samples. Microbial limits testing of non-sterile products. OOS results invalidated, retested or resampled without an assignable lab cause ("testing into compliance"). Inadequate Phase I (lab) investigation.
- **Excludes:** identity and other testing of incoming components (→ 9). Stability testing (→ 10). Sterility and endotoxin testing of sterile products (→ 7). Calibration of lab instruments (→ 6). The manufacturing-phase part of an OOS investigation (→ 4).
- **Boundaries:**
  - **OOS rule (vision):** OOS invalidated without an assignable lab cause, or an inadequate lab-phase investigation → **3**. Investigation not extended to manufacturing, no root cause, no or ineffective CAPA, other batches not reviewed → **4**. **Both** can apply to the same OOS. "OOS results were not investigated", with nothing about invalidation or the lab phase → 4 only.
  - vs **2:** see category 2.
  - vs **11:** a lab record lacking a required element (e.g. no sample weight) → 11. A test not performed at all → 3.
- **Typical citations:** 211.160; 211.165; 211.167(b), (c); 211.170; 211.194(a)–(c); Q7 11.1–11.4, 11.7, 12.8.
- **Examples:**
  - ✔ *The firm released finished drug products without testing assay and impurities.* → 3
  - ✔ *Initial failing assay results were attributed to analyst error without evidence and replaced by passing retest results.* → 3 (plus 4 if the letter also faults the lack of root cause or batch impact)
  - ✘ *The firm did not test incoming glycerin for diethylene glycol.* → 9.

### 4 · Investigations, deviations and CAPA

**Deviations, discrepancies, complaints, batch failures or OOS results were not thoroughly investigated: no root cause, no extension to manufacturing or other batches, no or ineffective CAPA.**

- **Includes:** unexplained discrepancies and batch failures (211.192). Deviations not documented or justified. Complaints not reviewed or investigated. Returned or salvaged products not evaluated. Recurring failures not trended or investigated. CAPA missing, late or ineffective (e.g. "retraining" as the only CAPA for a recurring equipment failure). Investigations not extended to other affected batches or products.
- **Excludes:** the lab phase of an OOS (→ 3, may co-occur). The firm's inadequate *response* to FDA (no label). A QU failure, unless the letter faults the QU (→ add 1).
- **Boundaries:**
  - vs **3:** OOS rule above.
  - vs **10:** a stability OOS poorly investigated → 4. Stability programme or expiry not adjusted after the failure → 10. Both if both are faulted.
  - vs **13:** "CAPA was limited to retraining" → 4, not 13.
- **Typical citations:** 211.192; 211.198; 211.100(b); 211.204; Q7 2.16, 8.15, 11.15, 15.
- **Examples:**
  - ✔ *The investigation into black particles in a tablet lot closed without a root cause, and other lots made on the same press were not evaluated.* → 4
  - ✔ *Customer complaints of broken tablets were logged but not investigated.* → 4
  - ✘ *"Your response does not include a retrospective review of released batches."* → no label: this is a response assessment.

### 5 · Process validation and production controls

**The manufacturing process is not validated or controlled: process validation, in-process controls, following master instructions, change control, reprocessing.**

- **Includes:** no process performance qualification before distribution; no ongoing or continued verification. In-process sampling and testing absent or inadequate. Time limits, yield, charge-in of components. Production procedures missing or not followed (subject rule). Changes to processes without change control. Reprocessing, rework and solvent recovery. Control of objectionable microorganisms in *non-sterile* production (211.113(a)). Blend uniformity. Fermentation and cell-culture process controls (API).
- **Excludes:** cleaning validation and equipment qualification (→ 6). Analytical method validation (→ 3). Aseptic process simulation and sterilisation validation (→ 7). Deviation investigation (→ 4).
- **Boundaries:**
  - vs **6:** does the failure concern the *process* (parameters, steps, validation of the product's manufacture) or the *equipment* (cleaning, qualification, maintenance)? Label accordingly; both if both.
  - vs **3 and 8 (non-sterile micro):** production controls against contamination → 5. Missing micro testing → 3. Water system as the source → 8.
  - vs **11:** master record *content* incomplete (missing steps, missing in-process limits) → 11. Operators *deviated* from the master record → 5.
- **Typical citations:** 211.100(a), (b); 211.101; 211.103; 211.110; 211.111; 211.113(a); 211.115; Q7 2.3, 8.1–8.4, 12.1, 12.2, 12.4–12.6, 13, 14.1–14.4, 18.
- **Examples:**
  - ✔ *The firm had not conducted process performance qualification for any product and could not show that its processes consistently produce acceptable quality.* → 5
  - ✔ *Operators changed the granulation mixing time from the master record without an approved change control.* → 5
  - ✘ *The firm had no data showing that cleaning of shared blenders removed product residues.* → 6.

### 6 · Cleaning and equipment

**Equipment cleaning (incl. validation), design, maintenance, calibration or qualification, and cross-contamination from shared equipment or facilities.**

- **Includes:** cleaning procedures not established or validated; visible residue; no residue or micro limits. Shared equipment or facilities with potent, sensitising or beta-lactam products without adequate controls. Unsuitable equipment design or materials. Preventive maintenance. Calibration, including lab instruments. Equipment qualification (IQ/OQ/PQ). **Computerised-system validation or qualification with no trust problem** (owner decision, v1.0).
- **Excludes:** sterilisation and depyrogenation of equipment and components for sterile products (→ 7). Building and room sanitation (→ 8). Access control, audit trail and backup of computer systems (→ 2). Utility qualification (HVAC, water) (→ 8).
- **Boundaries:**
  - vs **11:** equipment cleaning or use logs missing or incomplete → 11. Add 6 only if the letter faults the cleaning or maintenance itself (e.g. "not cleaned", "no evidence cleaning was effective").
  - vs **2 and 5:** see those categories.
- **Typical citations:** 211.42(d); 211.63; 211.65; 211.67; 211.68(a); 211.72; 211.160(b)(4); 211.176; 211.182; Q7 4.4, 5.1–5.3, 5.40–5.41, 8.5, 12.3, 12.7.
- **Examples:**
  - ✔ *The firm had no data showing that cleaning of a shared tablet press removed residues of a potent hormone product before non-hormone products were made.* → 6
  - ✔ *The HPLC used for release testing was months past its calibration due date.* → 6
  - ✘ *Peeling paint and a roof leak were observed above the manufacturing room.* → 8.

### 7 · Aseptic processing and sterility assurance

**Anything that threatens the sterility of products purporting to be sterile: aseptic practice, process simulation, sterilisation, airflow, classified areas, and sterility or endotoxin testing.**

- **Includes:** poor aseptic technique or gowning in or at the critical zone. Media fills (process simulation) inadequate or failed. Smoke studies or unidirectional airflow. Sterilisation, depyrogenation and filter validation or integrity. EM, cleaning and disinfection of classified areas (e.g. non-sterile disinfectants or wipes in ISO 5). **Any condition inside classified (ISO 5–8) areas serving sterile operations**, including building fabric (owner decision, v1.0). Sterility and endotoxin testing, and their failures or invalidations. Insanitary conditions affecting sterile compounding.
- **Excludes:** non-sterile micro control (→ 5 or 3). Unclassified areas, pests, general HVAC and water (→ 8), even at a sterile site. Training records (→ 13, may co-occur).
- **Boundaries:**
  - vs **8:** location decides. A condition in a classified area serving sterile operations → 7; anywhere else → 8. Water (WFI) or HVAC system design → 8 unless the letter ties it to a classified-area excursion.
  - vs **13:** gowning practice in aseptic areas → 7. Add 13 only if the letter faults training or qualification.
  - vs **3 and 4:** sterility-test positives invalidated without an assignable cause → 7 (in place of 3). Add 4 if the investigation's depth is faulted.
- **Typical citations:** 211.42(c)(10); 211.113(b); 211.167(a); FD&C 501(a)(2)(A).
- **Examples:**
  - ✔ *Operators reached over open vials in the ISO 5 filling zone and wore gowns with exposed skin at the wrists.* → 7
  - ✔ *Media fills did not simulate the maximum number of interventions performed in routine production.* → 7
  - ✘ *Purified water for an oral solution exceeded microbial action limits without follow-up.* → 8 (plus 4 for the lack of follow-up), not 7: the product isn't sterile.

### 8 · Facilities, utilities and environmental monitoring

**Building design, maintenance, cleanliness and pest control; HVAC; water and other utilities; EM outside classified sterile areas.**

- **Includes:** facility design, space and segregation to prevent mix-ups or contamination. Building repair, sanitation, pests. HVAC and compressed air. Purified water and other water systems (design, validation, monitoring). Lighting, plumbing, sewage. Non-sterile EM programmes. Insanitary conditions in unclassified areas, including at compounders.
- **Excludes:** classified areas serving sterile operations (→ 7). Equipment cleaning and cross-contamination through shared equipment (→ 6).
- **Boundaries:** vs **7** (location rule above). vs **6:** dedicated facilities or containment for penicillin or other sensitising products → 6 (plus 8 if the facility design itself is faulted).
- **Typical citations:** 211.42; 211.44–211.58; Q7 4; FD&C 501(a)(2)(A).
- **Examples:**
  - ✔ *Insects and bird droppings were observed in the warehouse next to open raw-material containers.* → 8
  - ✔ *The purified water system had not been validated and was not monitored for microbial quality.* → 8
  - ✘ *The ISO 7 buffer room ceiling had cracked, unsealed panels.* → 7 (classified area serving sterile operations).

### 9 · Supplier and component control

**Incoming components, containers and closures not tested, identity-verified or controlled; supplier CoA relied on without qualification; material storage and handling.**

- **Includes:** no identity test on each component lot. No DEG/EG testing of high-risk components (glycerin, propylene glycol, sorbitol, etc.); no methanol testing of high-risk ethanol or isopropanol. CoA accepted without validating the supplier's results. Container and closure testing and suitability. Quarantine, status, use and rejection of materials. Warehousing and storage conditions of materials and finished goods.
- **Excludes:** contract manufacturers and contract labs (→ 1). In-process testing (→ 5). Finished product release testing (→ 3). Depyrogenation or sterilisation of containers (→ 7).
- **Typical citations:** 211.80–211.94; 211.142; Q7 7, 9.2, 10.1.
- **Examples:**
  - ✔ *Each lot of glycerin was accepted on the supplier's certificate, without testing for diethylene glycol or qualifying the supplier.* → 9
  - ✔ *The firm did not perform an identity test on incoming API lots.* → 9
  - ✘ *Finished tablets were released without assay testing.* → 3.

### 10 · Stability and expiry

**No or inadequate stability programme, expiry or retest dates unsupported by data, or stability failures not acted on.**

- **Includes:** no written stability programme; no annual stability batch; methods not stability-indicating; no stability data at the labelled storage condition. Expiry or retest dates without supporting data. Product kept on the market or expiry not revised after stability failures. Missing stability records.
- **Excludes:** the quality of a stability-OOS investigation (→ 4). General method validation (→ 3).
- **Boundaries:** vs **4:** see category 4.
- **Typical citations:** 211.137; 211.166; 211.194(e); Q7 11.5, 11.6, 17.5.
- **Examples:**
  - ✔ *The firm assigned a 36-month expiry to its products without any supporting stability data.* → 10
  - ✔ *No batch of any product was placed on stability after its first year of marketing.* → 10
  - ✘ *The investigation of a 12-month impurity failure did not identify a root cause.* → 4 (plus 10 only if the letter also faults the programme or expiry).

### 11 · Batch records and documentation

**Records missing, incomplete or not reviewed; documents not controlled; record retention, with no suggestion that the records are untrustworthy.**

- **Includes:** master production records incomplete or unapproved. Executed batch records missing entries, signatures or equipment IDs. Component, labelling, distribution and equipment-use records incomplete. Document control: SOPs not approved, uncontrolled versions, no procedure system at all. Records not retained or not available. Lab records lacking required elements.
- **Excludes:** untrustworthy records (→ 2). A missing procedure for a specific function: label that function's category instead (owner decision, v1.0). Example: no cleaning SOP → 6, not 11. Release decisions (→ 1).
- **Boundaries:**
  - **Subject rule (owner decision, v1.0):** "The firm failed to establish or follow written procedures for X" → the category of X. Use 11 only when the fault is in the documentation system itself.
  - vs **2** and **5:** see those categories.
- **Typical citations:** 211.180(a)–(d); 211.182; 211.184; 211.186; 211.188; 211.196; Q7 6.
- **Examples:**
  - ✔ *Master production records lacked in-process limits and complete processing instructions for several products.* → 11
  - ✔ *Executed batch records were missing operator signatures and equipment identification for critical steps.* → 11
  - ✘ *Operators recorded weights on scrap paper that was discarded after the batch record was completed days later.* → 2.

### 12 · Packaging and labelling control

**Control of labels and packaging operations: issuance, examination, reconciliation, line clearance, mix-ups, tamper-evident packaging.**

- **Includes:** labels not examined or stored securely. Issuance and reconciliation discrepancies not investigated. No line clearance. Mixed strengths or products in a package. Packaged-product inspection. Tamper-evident OTC packaging. API repackaging and relabelling operations.
- **Excludes:** misbranding *claims* or legally deficient label content (→ no label, letter type). Container and closure quality (→ 9).
- **Typical citations:** 211.122; 211.125; 211.130; 211.132; 211.134; Q7 9, 17.4.
- **Examples:**
  - ✔ *Issued and used labels were not reconciled, and excess printed labels were not destroyed.* → 12
  - ✔ *No line clearance was done between packaging runs of two strengths; a bottle of the higher strength was found among the lower.* → 12
  - ✘ *The product label lacks adequate directions for use.* → no label (misbranding).

### 13 · Personnel and training

**Staff not trained, qualified or sufficient for their duties; hygiene and clothing outside sterile operations.**

- **Includes:** no GMP or job-specific training, or no training records for the tasks performed. Unqualified supervisors or analysts. Consultants' qualifications. Clothing, hair covers and hygiene in non-sterile production.
- **Excludes:** aseptic gowning and technique in classified areas (→ 7). Retraining as an inadequate CAPA (→ 4).
- **Boundaries:** vs **7** and **4:** see those categories. Tick 13 alongside 7 only when the letter faults training or qualification.
- **Typical citations:** 211.25; 211.28; 211.34; Q7 3.
- **Examples:**
  - ✔ *Analysts running release assays had no documented training in those methods.* → 13
  - ✔ *Production staff handled open product in street clothes without hair covers.* → 13
  - ✘ *Operators in the ISO 5 area had exposed skin between glove and sleeve.* → 7 (13 only if training is faulted).

---

## 4. Edge cases

### Repeat observations

- Label each repeated violation normally, like any other violation.
- **Owner decision, v1.0:** the "Repeat observations at facility" summary, and statements that repeats show inadequate management or QU oversight, create **no label**. That includes no automatic 1. Tick 1 only if a violation itself faults the QU.

### Multi-site letters

- One label set per letter: the union across all sites named in the violations. Quote from whichever site's observation is clearest. Don't try to separate sites. The letter is the unit.

### API / ICH Q7 letters

- Label by the described failure, exactly as for finished-dose letters. Observations often cite a Q7 section or no provision at all; that doesn't matter for gold.
- Q7 vocabulary: "quality unit" → 1. "Retest date" → 10. "Reprocessing, reworking, recovery of mother liquor or solvents" → 5. "Impurity profile" not compared or monitored → 3 (plus 5 if the process is faulted). "Agent, broker, repacker" operations → by subject (e.g. relabelling → 12, traceability records → 11).
- Letters to API *distributors or repackers*: label their own operations. "No oversight of the manufacturer" → 1 (contractor/supplier oversight by the contract giver). Plain CoA reliance for incoming material → 9.

### Compounding letters (503A and 503B)

- **503B (outsourcing facilities):** CGMP applies. Label like a finished-dose letter. Sterile operations are usually central → apply the category 7 location rule.
- **503A (pharmacies):** violations are often a bullet list of insanitary conditions, not numbered CGMP citations. Label each concrete condition by category: in or serving classified sterile-compounding areas (ISO 5 hood, buffer or ante room) → 7; unclassified rooms, pests, general building → 8. Gowning in the sterile area → 7; non-sterile hygiene → 13.
- The generic sentence "drugs were prepared, packed, or held under insanitary conditions…" (501(a)(2)(A)) creates no label on its own.
- Failure to meet 503A/503B *conditions* (patient-specific prescriptions, bulk substances, registration, reporting) and misbranding → no label.

### Letters citing only 501(a)(2)(B) generically

- Many API and foreign-site letters give numbered observations with no CFR citation. Label them by content as usual.
- If the letter contains **no described CGMP failure**, the label set is empty. Examples: it states adulteration under 501(a)(2)(B) only, refers to a refused or limited inspection (501(j)), or refers to records not provided under 704(a)(4).
- FDA's own test results on product samples (e.g. DEG or methanol found) are not violations by themselves. Label only the failures the letter attributes (e.g. "failed to test components" → 9).

### Other recurring patterns

- **Hand sanitiser and other OTC letters:** label normally. Methanol or benzene in incoming ethanol, isopropanol or carbomer not tested → 9. Finished product not tested → 3.
- **Contract testing labs as recipients:** their own lab failures → 3 (and 2 where applicable), not 1.

---

## 5. Label record

The tool saves `{letter_id, categories, quotes{cat: str}, labelled_at, guide_sha}` (`docs/decisions/0001-architecture.md`, *Labelling tool*). `guide_sha` is the sha256 of this file as labelled. The optional per-category `unsure` flag from [section 2](#rule-for-doubt) is not in that record yet; see [For the labelling-tool spec](#for-the-labelling-tool-spec).

---

## 6. Baseline mapping (`reference/cfr_map.csv`)

The deterministic baseline extracts 21 CFR, FD&C Act and ICH Q7 references from the letter and maps them through this table. Gold labelling never uses it.

**Format.** Columns `citation, category, rationale`. One row per (citation, category). An empty `category` means *recognised, maps to no category* (generic or non-CGMP provisions). Citation forms: `21 CFR 211.194(a)`, `21 CFR 11.10` (a part-level reference such as "21 CFR Part 11" becomes `21 CFR 11`), `FD&C 501(a)(2)(B)`, and `ICH Q7 <n>`, where `<n>` is a chapter (`11`), a section (`11.1`) or a paragraph (`11.15`).

**Lookup rule: most specific row wins.**

1. Normalise the extracted citation to the forms above.
2. If rows exist for the exact citation, use all of them and stop.
3. Otherwise, drop the last level and retry, down to the section. CFR drops the last parenthetical: `211.84(d)(1)` → `211.84(d)` → `211.84`. Q7 truncates a paragraph to its section, then its chapter: `7.31` → `7.3` → `7`. In the official text every paragraph is numbered `X.YZ` with two digits after the point and belongs to section `X.Y`, so truncation is unambiguous.
4. A citation with no row at any level maps to nothing and is logged as unmapped.
5. A letter's baseline label set is the union over all its citations.

**Bare sections.** A section or chapter row with no subdivision reflects how it is usually cited. Where its paragraphs are comparably weighted it maps to their union (e.g. 211.100 → 4, 5); otherwise it maps to its dominant subject (e.g. 211.194 → 2, 3 like 211.194(a); Q7 12 → 5). The rationale column says which.

**Where the map refines the vision's taxonomy column.** The CSV is authoritative for the baseline. Each difference is deliberate:

| Vision column | Map | Why |
|---|---|---|
| Q7 §15 as the only Q7 citation for 4 | adds Q7 2.16, 8.15, 11.15 → 4, and 14.5, 17.7, 17.8 | Q7 15 is *Complaints and Recalls* only; deviation and OOS investigation paragraphs sit in 2.1, 8.1 and 11.1 |
| Q7 §12 → 5 | 12.3 → 6, 12.7 → 6, 12.8 → 3; the rest → 5 | 12.3 is equipment qualification, 12.7 cleaning validation, 12.8 analytical method validation |
| Q7 §11.1–11.4 → 3 | also 11.7 (reserve samples); 11.3 kept | 11.3 is only a cross-reference to section 12 in the official text; its content is 12.8 |
| Q7 §2 → 1 | adds Q7 16 → 1; 2.3 → 5 | 16 is contract manufacturers and labs (vision: QU oversight of contractors); 2.3 covers production-unit responsibilities |
| Q7 §5.4 → 2 | 5.4 → 2, 6; 5.40–5.41 → 6 | owner decision: computerised-system validation without a trust problem → 6 |
| 211.182 → 6 | 211.182 → 6, 11; Q7 6.2 → 6, 11 | the baseline can't tell a cleaning failure from an incomplete log |
| 211.194(a) → 2 and 211.194 → 3 | 211.194(a) and bare 211.194 → 2, 3; (b)(c) → 3; (d) → 6; (e) → 10 | paragraph-level subjects |
| (not listed) | 211.42(d), Q7 4.4 → 6, 8; Q7 8.5 → 6; 211.176 → 6 | cross-contamination and containment |
| (not listed) | 211.160(b)(4) → 6 | calibration is category 6, including lab instruments |
| (not listed) | 21 CFR Part 11 and each of its 10 sections → 2 | owner decision: Part 11 governs the trustworthiness of electronic records and signatures. Known imprecision: 11.10(a) (system validation) also maps to 2, while gold labels functional validation without a trust problem as 6 |

**Verification sources.**

- **ICH Q7:** every Q7 section number and heading was checked against the official text, *ICH Q7 Good Manufacturing Practice Guide for Active Pharmaceutical Ingredients, Current Step 4 version dated 10 November 2000*, downloaded 2026-09-27 from `https://database.ich.org/sites/default/files/Q7%20Guideline.pdf` (sha256 `f28aff02d31b7edf6ed3026971a2283019ad51393165ffbc5efb5ae7208e1f1e`, 49 pages). Each Q7 row's rationale gives the heading and the PDF page where it appears.
- **21 CFR 11/210/211:** section titles and paragraph designations were checked against eCFR, Title 21 as up to date on 2026-09-24 (`https://www.ecfr.gov/api/versioner/v1/`).
- **FD&C Act rows:** the provisions that recur in CDER drug warning letters. All of them map to no category except 501(a)(2)(A).

---

## 7. Pilot and freeze

Before any sample letter is labelled, the guide is tried on real letters and then frozen.

1. **Pick 5 pilot letters from outside the 150-letter sample.** Do this after the sample and split files are drawn, so "outside" can be checked against them. Cover different letter types where possible (at least one API and one compounding letter) and different fiscal years. Record the pilot letter IDs in a file under `evaluation/splits/`.
2. **Label them with the labelling tool under this guide.** Follow section 2 exactly, including quotes and the unsure flag. Time each letter; this is the first data for the 6-minute pace check. Don't look at model or baseline output for these letters first.
3. **Fix what was unclear.** Edit the guide, and the map if a mapping problem shows up. Every change gets a changelog row, even though no sample letter has been labelled yet.
4. **Freeze as v1.1.** Set the header to `Version 1.1` and status *frozen*. Commit the guide and `reference/cfr_map.csv` together, then tag that commit `labelling-guide-v1.1` (annotated tag). The tag message records the sha256 of both files; the freeze changelog row records the map's sha256. The freeze must land before any model output exists (`docs/vision.md`, evaluation protocol step 1).
5. **Pilot letters are excluded from evaluation.** Their labels are kept apart from sample gold and never enter gold, splits, metrics, κ or the search questions. They need no re-check after changes.

Sample labelling starts only at the v1.1 tag, and every sample label must carry the v1.1 `guide_sha` or a later changelogged version.

---

## 8. Change control

- This guide and `reference/cfr_map.csv` are versioned in git and frozen together. The labelling tool records this file's sha256 with every label, so every gold label traces to the exact guide text it was made under.
- **Before the v1.1 freeze:** edits are normal commits, each logged in the changelog (see section 7).
- **After the v1.1 freeze:** every change, however small, needs:
  1. a changelog entry below (date, version, what changed, why, categories affected);
  2. a version bump (minor for clarifications, major for a changed boundary);
  3. a re-check of every letter already labelled, **for the affected categories only**, recorded as new label lines (never edits to earlier lines) under the new `guide_sha`.
- **Test gold is never edited after results are seen** (`docs/vision.md`). A boundary problem found then is fixed in the next version of the guide, and the flawed version is reported with the results.
- A change to `reference/cfr_map.csv` after any model output exists changes the baseline. It is logged here and reported in the evaluation.

## Changelog

| Date | Version | Change | Categories affected | Re-check done |
|---|---|---|---|---|
| 2026-09-27 | 1.0 | Initial version, paired with `reference/cfr_map.csv` v1. Owner decisions: subject rule for procedures (11); computerised-system validation → 6 unless trust (2/6); classified-area conditions → 7 (7/8); repeat-observation summaries → no label (1). | all | n/a (before labelling) |
| 2026-09-27 | 1.0 | Before labelling: added 21 CFR Part 11 to the map (part level plus sections 11.1–11.300 → 2; 11 rows) and to category 2's typical citations; added section 7 *Pilot and freeze*; added the labelling-tool spec note. | 2 (baseline only) | n/a (before labelling) |

---

## For the labelling-tool spec

These are requirements this guide places on the labelling tool. They aren't in `docs/decisions/0001-architecture.md` yet; that record is owned by the collector branch.

- **`unsure` field.** Add an optional per-category flag to each saved record, e.g. `unsure: [<category>, …]`, where each entry is a category number 1–13, ticked or not. It is saved with the label, never changes `categories`, and is ignored by scoring. It is read afterwards alongside the self-consistency κ to find ill-defined boundaries.
- **Pilot flag.** Pilot labels (section 7) must be distinguishable from sample gold, either in a separate file or marked `pilot: true`, so they can never enter evaluation.
- **Guide version check.** The tool should refuse to label a sample letter unless the current guide sha256 matches the v1.1 freeze or a later changelogged version.
