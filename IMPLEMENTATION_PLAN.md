# Mosam Client Issues and Implementation Plan

## Credit-Safe Completion Plan - 23 July 2026

### Decision

OpenAI paid development tests are frozen because the latest seven-product run ended with
`insufficient_quota`. All remaining implementation and verification will use local TEC data,
mocked provider responses, cached classifications, and offline regression suites. No 25- or
40-product paid rerun is required to finish engineering.

### Latest measured state

- cache schemas are full request `v17` and item `v12`
- the seven-product run reduced query embeddings from 14 to 7
- batches 1 and 2 completed and stored six item-cache results
- batch 3 stopped before classifying the seventh item because OpenAI returned HTTP 429
- the run used two classification calls before quota exhaustion
- telemetry recorded `structured_validated_examples_skipped=6`
- the next identical run should reuse six item-cache records and process only the remaining item

### Completion phases

| Phase | Scope | Verification method | Status |
|---|---|---|---|
| P0 | Reproducible 7/25/client benchmark fixtures | Local benchmark loaders and scorers | Complete |
| P1 | Import, batching, item cache, warm fast path, telemetry | Offline API/cache tests | Complete |
| P2 | Typed product evidence and generic technical nature | Tariff-neutral unit tests | Complete |
| P3 | TEC candidate retrieval and chapter-first hierarchy | Candidate/hierarchy regression tests | Complete offline |
| P4 | Functional contradiction, confidence, completeness and RGI coherence | Decision/coherence/subposition tests | Complete offline |
| P5 | Manufacturer-reference identification and bounded web escalation | Mocked web/provider tests | Complete offline |
| P6 | Quota/rate-limit partial-result resilience and retry UX | Mocked 429 tests plus TypeScript check | Complete |
| P7 | External cache, database and final live acceptance | One bounded live run after services/credit are available | Pending external acceptance |

### P6 behavior delivered

- a recognized OpenAI quota, rate-limit, timeout, or connection failure no longer discards already
  completed batch results
- successful item results remain cached
- failed and not-yet-started rows are returned as explicit provisional, retryable rows
- after a sequential provider failure, remaining batches do not make additional provider calls
- parallel manufacturer-reference failures use the same retryable error contract
- frontend prevents validation of retryable rows, displays a clear waiting state, and offers a retry
- retry reuses successful item-cache entries and therefore processes only missing rows
- unexpected programming errors are still raised and are not silently converted into placeholders

### Zero-credit verification gate

- backend: 265 offline tests pass; five live Upstash integration tests are skipped
- focused quota/quality/cache/acceptance suite: 73 tests pass
- frontend: `npx tsc --noEmit` passes
- Python compile and `git diff --check` pass
- no OpenAI request was made by these verification commands

### Only remaining paid acceptance

After OpenAI credit is restored:

1. restart the backend once
2. import `sample_client_regression_7.csv`
3. run the same seven products once; expected cache state is six hits and one pending item
4. export the JSON and preserve telemetry
5. rerun the same seven products once to confirm seven item-cache hits and zero classification calls
6. do not run the 25- or 40-product suites unless the seven-product gate exposes a regression

### Automated final acceptance

The final run is scored locally and does not make an OpenAI request. Preserve the exported JSON and
backend log, then run:

```powershell
python -m sam.final_acceptance --results <selective-results.json> --log <selective-run.log> --mode selective --report final-selective-report.json
python -m sam.final_acceptance --results <warm-results.json> --log <warm-run.log> --mode warm --report final-warm-report.json
```

The selective gate requires seven results, no retryable/blank/forbidden outcome, at least six accepted
quality outcomes, at least six candidate-recall matches, at least six item-cache hits, no more than one
classification call, and no more than one query embedding. The warm gate additionally requires seven
cache hits (or a full-request cache hit), zero classification calls, and zero query embeddings. A non-zero
command exit code means the release gate failed and the 25/40-product suites must not be started.

### Final acceptance gates

- seven response rows for seven inputs
- no forbidden client-reported heading
- no confirmed blank/placeholder code
- unresolved products remain provisional with the missing discriminant stated
- first acceptance run performs only the minimum uncached work
- immediate repeat performs zero OpenAI classification and web-search calls
- live Upstash cache and Supabase validation/history checks pass in the deployment environment

### Scope boundary

Engineering can be completed and delivered without more paid tests, but customs accuracy cannot be
claimed as universally guaranteed. The final seven-item output and ambiguous professional-equipment
subpositions still require the documented customs-expert acceptance review.

## Cost-controlled test suites

- Run `sample_client_regression_7.csv` for normal development feedback.
- Run `sample_manufacturer_references_10.csv` only when identification or web-search behavior changes.
- Run `sample_products_quality_25_fresh.csv` at quality milestones and before release, not after every edit.
- Reserve the external 40-product client list for final cold acceptance testing.
- Expected benchmark CSVs under `sam/benchmarks/` are local scoring fixtures and do not consume OpenAI tokens.

## 1. Executive Summary

This document separates product issues from the general technical documentation and turns them into an actionable implementation plan.

## Current Quality Completion Plan - 21 July 2026

### Objective

Keep the completed cost, cache, import, and batch improvements while correcting the functional-classification failures reported by the client for professional equipment.

The quality phase will not add production mappings such as `Cisco Catalyst 9300 -> 8517.62`. Client products will be retained only as regression inputs. Production decisions must be based on product function, official TEC candidates, legal criteria, and evidence quality.

### Confirmed failure pattern

The latest 40-product export showed that the pipeline can return one row per product at low repeated cost, but it can still select a semantically incompatible heading and assign high confidence to it.

Examples reported by the client include:

| Functional product type | Observed failure |
|---|---|
| Ethernet switch | smartphone heading |
| complete storage array | recording-media heading |
| multispectral/thermal camera | smartphone heading |
| tablet computer | smartphone assumed without resolving capabilities |
| industrial robot | motorcycle/bicycle-parts heading |
| programmable controller | generic-computer heading |
| variable-frequency drive | no usable position |

The current position validator is mainly lexical and preserves already-confirmed results above its confidence threshold. Consequently, an incorrect exact candidate can survive with `95%` confidence even when its official label conflicts with the supplied function.

### Non-negotiable design rules

- no manufacturer, model, or part-number-to-HS mapping in production code
- no complete manually maintained product database
- client examples may appear in tests, never as runtime answers
- official TEC labels and notes remain the tariff source of truth
- external search identifies the product; it does not directly decide the tariff code
- rich structured inputs avoid web search unless evidence is contradictory or materially incomplete
- the cheaper model remains the default
- a stronger model is used only for bounded ambiguous or contradictory cases
- an uncertain partial result is preferable to a confident incompatible result
- no blank or placeholder HS code may be stored as validated history

### Phase Q0. Clean baseline and benchmark labels

**Work**

- restart and verify full-request cache `v10` and item cache `v5`
- rerun the 40 detailed products and preserve logs plus exported JSON
- convert the seven client-reviewed examples into a non-official engineering benchmark
- record expected functional family, allowed chapter/heading candidates, forbidden headings, and rationale
- mark the iPad/tablet case as conditional rather than forcing one answer without capability evidence

**Deliverables**

- client-feedback benchmark data file
- baseline quality report
- baseline cost, latency, cache, and model telemetry

**Exit gate**

- benchmark can automatically detect all seven reported failure patterns
- test data clearly states that expected headings require customs-expert confirmation

### Phase Q1. Structured functional profile

**Work**

- add a product-understanding stage that produces structured fields before tariff retrieval
- capture primary function, product class, standalone system versus component, input/output behavior, communication capability, storage behavior, control behavior, imaging behavior, power-conversion behavior, and missing discriminants
- build the profile from frontend fields first and cached/external identification second
- preserve evidence source and identification confidence for every profile field
- generate retrieval queries from function and capabilities instead of relying mainly on brand, model, material, or generic words

**Implementation direction**

- use a schema-driven profile, not product-specific conditions
- keep profile extraction batchable and cacheable
- do not place an HS code in the functional-profile output

**Exit gate**

- all seven client examples receive the correct general functional description
- no tariff code is selected during this stage
- repeated profiles are served from cache

### Phase Q2. Candidate retrieval and recall measurement

**Work**

- retrieve TEC candidates using separate queries for primary function, product class, capabilities, and system/component status
- merge and deduplicate candidates while retaining source scores
- ensure candidate diversity so one weak semantic family cannot occupy every slot
- add candidate-recall telemetry showing whether the expected benchmark heading appeared in top-k
- prevent a full confirmed result when candidate evidence is weak or mutually inconsistent

**Why this phase comes before final classification**

If the legally relevant heading is absent from the candidate set, changing the final prompt or model cannot reliably fix the answer. Candidate recall must be measured independently from final-code accuracy.

**Exit gate**

- expected heading appears in top-k for at least 6 of the 7 client examples
- the conditional tablet case includes both legally plausible families when required facts are unavailable
- every candidate shown to the model includes an official TEC label or source excerpt

**Implementation status - 22 July 2026**

- candidate affinity, source metadata, deduplication, and bounded chapter diversity are implemented
- candidate-recall telemetry and offline benchmark scoring are implemented
- weak in-set selections are provisional and confidence-capped
- pre-change client export measures 4/7 candidate-position recall
- fixed tariff-code examples were removed from the classifier output contract to prevent prompt anchoring
- exit gate remains pending a fresh `v12`/`v7` live run

### Phase Q3. Semantic contradiction and confidence gate

**Work**

- compare the functional profile against the selected official TEC heading and subheading labels
- classify compatibility as compatible, incompatible, or unresolved with a short evidence-based reason
- reject incompatible high-confidence results before response assembly
- retry selection from the remaining retrieved candidates when the first choice is incompatible
- return a provisional heading and missing-information request when compatibility cannot be established
- calculate displayed confidence from identification confidence, candidate evidence, semantic compatibility, and subheading completeness

**Generic contradictions to detect**

- product function is data switching while selected line describes smartphones
- product is a complete system while selected line describes removable or recording media
- product captures images while selected line describes telephones
- product performs industrial control while selected line describes general computing without supporting evidence
- product is industrial machinery while selected chapter is vehicle parts

These are functional consistency checks, not brand or model mappings.

**Exit gate**

- zero forbidden-heading outcomes across the seven client examples
- no semantically incompatible result can retain confidence above 55
- blank results become explicit provisional outcomes with missing evidence
- confirmed status requires successful compatibility and completeness checks

### Phase Q4. Selective model and web escalation

**Work**

- keep `gpt-4.1-mini` as the default classification model where configured
- escalate only when the contradiction gate fails, top candidates are close, or required discriminants are missing
- batch compatibility checks where possible
- use external product search only when technical identity or a decisive specification cannot be established from the supplied rich fields
- cap retries, web searches, and stronger-model calls per request
- cache functional profiles, identification evidence, and resolved ambiguity separately

**Telemetry**

- `functional_profile_calls`
- `candidate_recall_top_k`
- `semantic_contradictions`
- `candidate_reselection_attempts`
- `quality_escalation_calls`
- `quality_escalation_reason`
- `quality_unresolved_items`

**Exit gate**

- normal detailed rows do not trigger external search
- stronger-model escalation remains bounded to genuinely ambiguous items
- a repeated identical request uses zero new classification, profile, or web-search calls when caches are valid

### Phase Q5. Regression, acceptance, and rollout

**Automated suites**

- client seven-product functional regression suite
- existing 25-product quality benchmark
- full 40-product structured dataset
- sparse manufacturer-reference dataset
- cache cold, partial-cache, and fully warm scenarios
- validation-storage tests for blank and provisional codes

**Quality acceptance**

- one output row for every valid input row
- zero blank HS values presented as confirmed
- zero client-reported forbidden-heading regressions
- at least 6 of 7 client examples reach expected heading or a legally safe conditional outcome
- all high-confidence results pass semantic compatibility checks
- every unresolved result states the missing discriminating information

**Cost and performance acceptance**

- 40 rich rows use configured small batches and no unnecessary web search
- cold classification calls remain at or below the normal batch count plus explicitly logged escalations
- escalation count and reason are visible in telemetry
- warm repeated test uses zero OpenAI calls when all cache entries are valid
- no quality fix is accepted if it silently restores the previous per-item 40-call path

**Release process**

- run changes behind a configurable quality-gate flag
- compare baseline and new outputs before enabling by default
- invalidate only quality-affected cache schemas
- retain rollback to the previous classifier while preserving import, history, and telemetry improvements
- update the single client-facing change document after measured acceptance passes

### Proposed implementation order and estimate

| Order | Phase | Engineering estimate | Primary result |
|---:|---|---:|---|
| 1 | Q0 baseline and benchmark | 0.5-1 day | reproducible client-quality baseline |
| 2 | Q1 functional profile | 1.5-2 days | structured product understanding |
| 3 | Q2 candidate retrieval | 1.5-2 days | relevant headings consistently available |
| 4 | Q3 contradiction/confidence gate | 2-3 days | incompatible answers blocked |
| 5 | Q4 selective escalation | 1-2 days | quality recovery with bounded cost |
| 6 | Q5 acceptance and rollout | 1-2 days | measured release decision |

Estimated total: approximately 8-12 engineering days, depending on customs-expert review turnaround and the number of ambiguous TEC subheading cases discovered during testing.

### Immediate next action

Begin Q0 and Q1 together: establish the clean `v10/v5` baseline, create the client-feedback benchmark, and implement the tariff-neutral functional-profile schema. Do not add runtime product-to-code mappings while doing this work.

The client raised two main concerns in the meeting:

- API cost is too high
- results are not good enough

Based on the current codebase, the recommended order of work is:

1. reduce API cost and response time first
2. optimize the current pipeline
3. improve classification quality
4. strengthen manufacturer and part-number handling
5. stabilize multi-product flows
6. strengthen document and invoice import

## 2. Priority Issues

### Priority 1. High API cost

Business impact:

- one product can reportedly cost more than USD 1
- multi-product uploads scale poorly
- this threatens adoption and commercial viability

Likely causes in the current system:

- multiple LLM stages per request
- web search enabled too broadly
- expensive fallback behavior in file classification
- limited caching of expensive intermediate work
- repeated work across identification, retrieval, and final classification

### Priority 2. Slow response time

Business impact:

- slow answers reduce trust
- latency makes cost feel even worse
- uploads become frustrating for users

Likely causes in the current system:

- sequential processing pipeline
- optional web-search latency
- batch processing with per-item fallback
- heavy model usage where cheaper routing may be enough

### Priority 3. Optimization of the current pipeline

Business impact:

- this is the fastest path to improve cost and time before building larger new subsystems

Likely causes in the current system:

- no strong request routing by complexity
- no aggressive memoization of intermediate outputs
- repeated model work on similar inputs
- fallback patterns that improve completeness but hurt cost and latency

### Priority 4. Manufacturer / part-number classification

Business impact:

- a common real-world user flow is to submit a part number or manufacturer reference
- weak handling here directly hurts trust in classification quality

Likely causes in the current system:

- identification still depends heavily on LLM reasoning and optional web search
- no dedicated internal reference catalog
- no deterministic mapping from resolved product to tariff candidates

### Priority 5. Incomplete or incorrect classification

Business impact:

- wrong or incomplete subpositions undermine the product's main promise

Likely causes in the current system:

- ambiguous upstream product identification
- incomplete structured evidence for fine-grained tariff selection
- difficult edge cases still depend on model interpretation

### Priority 6. Batch / multi-product stability

Business impact:

- users often classify multiple products together
- inconsistent batch outputs increase manual verification work

Likely causes in the current system:

- model outputs are not fully deterministic across all batch cases
- batch fallback improves completeness but increases operational instability

### Priority 7. Reliable file import

Business impact:

- many users work from invoices and spreadsheets, not manual text entry

Likely causes in the current system:

- PDF handling is mostly text extraction based
- scanned documents are not fully supported
- invoice table understanding is not yet a dedicated extraction subsystem

## 3. Root-Cause Mapping

### Why API cost is high

The strongest contributing causes are:

- expensive model usage for both identification and classification
- web search being active in cases where it may not be necessary
- file batch fallback turning one upload into many extra model calls
- insufficient caching of intermediate results
- repeated processing of similar products

### Why results are not good enough

The strongest contributing causes are:

- weak deterministic handling of manufacturer references and part numbers
- incomplete or incorrect subposition selection in hard cases
- noisy extraction from uploaded files and invoices
- instability in batch outputs

## 4. Implementation Strategy

The plan should be delivered in phases. The first phases focus on cost and performance because they are the fastest to improve and directly address the client's top complaint. Quality improvements should happen in parallel where they support those same goals.

### Optimization Principles

The optimization strategy should reduce cost and latency without damaging classification quality. The preferred methods are:

- smart routing so simple requests do not use the most expensive path
- controlled web search only for cases that genuinely need it
- multi-level caching for identification, single-item classification, and repeated upload items
- confidence-based escalation so hard cases still use the stronger path
- deterministic rules before LLM reasoning wherever possible
- part-number lookup-first handling for repeat industrial references
- better batch orchestration to reduce expensive fallback behavior

These methods are preferred because they reduce wasted model usage while preserving a strong path for difficult cases.

### Phase 0. Baseline and Measurement

Goal:

- establish hard metrics before changing behavior

Deliverables:

- per-request cost logging
- per-stage latency logging
- batch fallback rate logging
- web-search usage rate logging
- cache hit and miss logging
- a small benchmark dataset for single-item, multi-item, part-number, and invoice cases

Acceptance criteria:

- team can answer these questions with data:
- average cost per request
- average cost per item
- p50 and p95 latency
- how often web search is used
- how often batch fallback is triggered

### Phase 1. Cost and Time Reduction

Goal:

- reduce cost and latency without changing the business workflow

Work items:

- route simple inputs to a cheaper identification model
- route simple final classification cases to a cheaper classification model where safe
- disable web search by default for low-risk cases
- only enable web search for manufacturer references or very short ambiguous inputs
- cap retries on manufacturer-reference identification
- reduce duplicate processing between identification and classification
- improve cache coverage for intermediate steps such as product identification
- add cache keys for normalized item-level classification in file uploads

Acceptance criteria:

- cost per single-product request reduced materially
- average response time reduced materially
- no increase in classification failure rate on the benchmark dataset

Expected outcome:

- fastest visible improvement for the client

### Phase 2. Pipeline Optimization

Goal:

- make the existing architecture more efficient before adding big new features

Work items:

- introduce request complexity scoring
- skip unnecessary pipeline stages for rich user inputs
- avoid web-search calls when the input is already detailed enough
- reduce repeated prompt construction and repeated retrieval work
- improve batch orchestration so repeated items reuse cached item-level outputs
- tighten fallback thresholds for batch mode
- expand model routing rules only after benchmark validation confirms quality is preserved

Acceptance criteria:

- lower batch fallback rate
- lower average model calls per request
- lower average latency for multi-product uploads

### Phase 3. Classification Quality Improvement

Goal:

- improve correctness and subposition completeness on single-item flows

Work items:

- build an evaluation set of real client examples
- separate quality failures by category:
- wrong product identification
- wrong chapter
- wrong heading
- wrong subheading
- missing national line
- strengthen evidence passed into final classification
- improve candidate narrowing before the final model step
- add stricter confidence and abstention behavior for uncertain outputs
- add quality regression tests for known bad cases

Acceptance criteria:

- benchmark accuracy improves on the agreed sample set
- fewer incomplete subposition outputs
- fewer low-confidence wrong answers

### Phase 4. Manufacturer and Part-Number Resolution

Goal:

- move from mostly LLM-based part-number identification to a more deterministic flow

Work items:

- create a product reference table for manufacturer references
- store canonical product attributes:
- manufacturer
- part number
- product type
- family
- core specs
- known candidate HS/TEC positions
- add a lookup-first flow:
- first query reference data
- only call LLM when lookup confidence is low
- capture validated user corrections into the reference table

Acceptance criteria:

- repeat manufacturer references resolve without web search
- cost for known part numbers drops sharply
- quality for known industrial references improves

### Phase 5. Batch and Multi-Product Stabilization

Goal:

- make uploads and multi-line requests operationally reliable

Work items:

- classify distinct items at item level, then aggregate quantities separately
- persist item-level results for reuse across uploads
- add bounded concurrency for batch classification
- add retry rules that do not immediately fall back to the most expensive path
- improve batch completeness validation before triggering per-item fallback

Acceptance criteria:

- lower batch failure rate
- lower per-upload cost
- more stable classification count per uploaded item list

### Phase 6. Document and Invoice Import

Goal:

- improve extraction quality from business documents

Work items:

- separate digital PDF flow from scanned PDF flow
- add OCR for scanned documents
- add table extraction logic for invoice layouts
- build structured document extraction outputs before classification
- add asynchronous processing for large documents

Acceptance criteria:

- improved extraction quality on invoice samples
- lower manual cleanup before classification
- fewer noisy product lines entering the classification engine

## 5. Proposed Delivery Plan

### Sprint 1

Focus:

- measurement, cost logging, latency logging, cache metrics
- model routing audit
- web-search gating changes

Expected result:

- baseline dashboard
- first cost reduction

### Sprint 2

Focus:

- intermediate caching
- item-level cache for uploads
- batch fallback reduction

Expected result:

- lower multi-product cost
- faster uploads

### Sprint 3

Focus:

- quality benchmark dataset
- candidate narrowing improvements
- confidence and abstention tuning

Expected result:

- better single-product quality

### Sprint 4

Focus:

- part-number lookup table
- lookup-first resolution path
- validated correction capture

Expected result:

- better manufacturer-reference accuracy
- lower cost for repeat industrial products

### Sprint 5

Focus:

- batch stability hardening
- concurrency and orchestration improvements

Expected result:

- more reliable multi-product processing

### Sprint 6

Focus:

- OCR and invoice extraction improvements
- async import processing

Expected result:

- stronger file-import pipeline

## 6. Technical Work Breakdown

### Backend

- add cost and latency instrumentation in `sam/api.py`
- add item-level and intermediate cache support
- add routing logic for low-cost vs high-cost paths
- add lookup-first manufacturer-reference flow
- improve batch orchestration in `/classify/file`

### Data

- create a reference dataset for manufacturer and part-number mapping
- create a benchmark dataset from real client samples
- create regression cases for known failures

### Frontend

- surface clearer progress states for uploads
- expose when a result is provisional or low-confidence
- show better guidance when a file import needs cleanup

### Operations

- define a cost budget per item and per upload
- define quality metrics and release gates
- monitor web-search rate, fallback rate, and cache hit rate

## 7. Risks and Dependencies

### Main risks

- reducing cost too aggressively may harm quality if routing is not controlled
- better quality may require real labeled examples from the client
- part-number resolution quality depends on building or acquiring reference data
- invoice extraction quality depends on document variety and OCR quality

### Dependencies

- access to representative client samples
- agreement on acceptable cost per product
- agreement on target latency
- agreement on quality metric and acceptance threshold

## 8. Current Completion Position

The main architecture and optimization controls are now implemented. The remaining work is no longer broad feature development; it is focused on closing measurable gaps and proving that the optimized flow meets the agreed client scope.

Completed foundations include:

- classification, product-identification, web-search, cache, token, and duration telemetry
- lower-cost model routing and targeted web-search policy
- product-identification cache normalized by manufacturer reference
- compact TEC/RAG context with quality-safety limits
- small-batch processing for normal structured products
- stable per-item processing with limited parallelism for manufacturer references
- CSV/Excel import, multilingual header mapping, template download, and numeric validation
- frontend progress visibility and manufacturer-identification traceability
- backend validation storage and admin history for validated results

Latest manufacturer-reference test evidence:

- 10 manufacturer references were detected and classified
- 9 of 10 product-identification lookups were served from cache
- only 1 web-search call was required
- all classification calls used the configured lower-cost model
- two reference items were processed concurrently
- total wall-clock time was approximately 4 minutes 45 seconds
- the remaining cache gap was `structured_item_cache_hit=0`, resulting in 10 classification LLM calls

## 9. Remaining Completion Plan

### Phase 1. Complete Single-Item Classification Cache

Priority: Critical

Status: Implemented and verified through live structured `/classify/stream` runs. The current `v4` cache needs one warm-repeat confirmation before release sign-off.

Objective:

- prevent repeated manufacturer references from triggering a new classification LLM call when a valid cached classification already exists

Implementation tasks:

1. add diagnostic logs around single-item classification cache key generation, read, decode, write, and expiry
2. verify that cache read and write paths use exactly the same normalized manufacturer-reference key
3. add telemetry counters for item-cache load hit, load miss, successful store, invalid entry, and store failure
4. add unit tests covering bare references, labelled references, imported structured rows, and rows with changed commercial fields
5. run the same 10-reference CSV twice after a backend restart

Acceptance criteria:

- first run stores one valid item-level classification per unique reference
- second identical run reports at least 9 of 10 `structured_item_cache_hit`
- second run makes no more than 1 classification LLM call unless a cached entry is invalid
- cached responses preserve quantity, origin, value, currency, and other request-specific commercial fields correctly

Implementation result:

- root cause fixed: `cache_get()` treated every JSON object containing a business `value` field as a legacy `{ "value": ... }` wrapper
- valid cached classifications were therefore reduced to values such as `2850 USD` and rejected by the item-cache loader
- legacy wrapper detection now applies only when `value` is the object's only key
- item cache reads and writes now expose hit, miss, invalid, store, skipped, and failed telemetry
- invalid/placeholder classifications are not persisted
- current request quantity, origin, and value overwrite cached commercial metadata safely
- numeric-only labelled references are normalized and old full-text keys migrate automatically
- cache reads and multi-item writes use bounded I/O concurrency
- live cache verification returned 10 of 10 hits; the second normalized read completed in approximately 3.42 seconds

### Phase 2. Establish Classification Quality Benchmark

Priority: Critical

Status: Benchmark tooling and the post-fix `v4` cold comparison are complete. `v4` is the accepted engineering baseline at 56% exact HS6, 84% heading, and 88% chapter accuracy; customs-expert validation of reference labels is still pending.

Objective:

- prove that cost and prompt reductions have not materially reduced tariff-classification quality

Implementation tasks:

1. create a versioned benchmark containing normal descriptions, manufacturer references, ambiguous products, and known difficult TEC subpositions
2. record expected chapter, heading, subheading, and final tariff line where expert-confirmed labels are available
3. add automated comparison for exact code, heading-level match, completeness, and low-confidence handling
4. classify failures by product identification, retrieval, legal-rule interpretation, missing product information, or output-format failure
5. tune RAG context and routing only against benchmark evidence

Acceptance criteria:

- every benchmark input produces one corresponding result
- no silent missing products in multi-product requests
- manufacturer references are identified or explicitly marked unresolved
- no regression against the current baseline at chapter and heading level
- final-line accuracy target is agreed with the client or customs-domain reviewer before production acceptance

Dependency:

- final tariff-code accuracy cannot be honestly certified without expert-confirmed expected codes for representative client products

Implemented benchmark workflow:

1. import and classify `sample_products_quality_25_fresh.csv`
2. download the machine-readable result from the result-panel `JSON` button
3. run `python -m sam.quality_benchmark --results <downloaded-results.json> --report quality_benchmark_report.csv`
4. review exact HS6, heading-or-better, chapter-or-better, missing-code, and mismatch metrics
5. inspect each mismatch in the report before changing retrieval, prompts, or model routing

Quality safety rule:

- `quality_benchmark_25_expected.csv` is an engineering reference set, not an official customs ruling
- its expected codes must be reviewed by a customs-domain expert before using final-line accuracy as a production acceptance claim

First measured baseline:

- completeness: 25/25 results, with no missing result or missing code
- exact HS6: 10/25 (40%)
- heading-or-better: 16/25 (64%)
- chapter-or-better: 21/25 (84%)
- severe chapter mismatch: 4/25 (16%)
- measured warm-cache latency: 8.73 seconds for 25 products
- measured warm-cache paid usage: zero LLM calls, zero web searches, and zero prompt/completion tokens

Post-guard `v3` comparison:

- exact HS6: 7/25 (28%), down from 40%
- heading-or-better: 15/25 (60%), down from 64%
- chapter-or-better: 22/25 (88%), up from 84%
- severe chapter mismatch: 3/25 (12%), down from 16%
- decision: rejected as the release configuration because exact and heading-level quality regressed
- follow-up: lexical position mutation removed in cache schema `v4`; the validator now records advisory evidence without changing the selected HS code

Accepted `v4` quality baseline:

- exact HS6: 14/25 (56%), up from the original 40% and rejected `v3` 28%
- heading-or-better: 21/25 (84%), up from 64% and 60%
- chapter-or-better: 22/25 (88%), up from 84% and equal to `v3`
- severe chapter mismatch: 3/25 (12%)
- completeness: 25/25, with no missing result or missing code
- decision: accepted as the current engineering baseline; do not change general routing or validator behavior without passing this benchmark
- remaining targeted cases: vacuum flask, LED bulb, woven polypropylene sack, and HS 2022 subheading resolution

Current targeted baseline after `heading-v1`:

- exact HS6: 14/25 (56%)
- heading-or-better: 23/25 (92%)
- chapter-or-better: 24/25 (96%)
- LED bulb improved from `94.05` to `85.39`
- woven packing sack improved from `39.02` to `63.05`
- only one severe mismatch remains: stainless steel vacuum flask
- next retry is vacuum-only through item-cache namespace `heading-v2`

Accepted targeted baseline after `heading-v2`:

- exact HS6: 14/25 (56%)
- heading-or-better: 24/25 (96%)
- chapter-or-better: 25/25 (100%)
- severe chapter mismatches: 0
- vacuum flask improved from `73.23` to correct heading `96.17`
- only one product remains below heading level: glazed ceramic floor tile, currently on legacy `69.08`
- next quality phase is HS 2022 subheading/legacy-code resolution; broad candidate and validator changes are frozen

Targeted severe-mismatch iteration:

- structured rows now apply local customs aliases and TEC heading matching even when paid product identification is skipped
- local official-heading verification resolves vacuum flask to `96.17`, LED bulb to `85.39`, and woven packing sack to `63.05`
- no additional embedding, web-search, or LLM call is added by heading enrichment
- full-request cache is `v5`, while item-cache invalidation is selective: 22 benchmark items retain `v4` and only the three targeted families use `v5`
- expected next validation path: 22 item-cache hits, 3 misses, and one three-item classification batch

### Phase 3. Final Cost and Response-Time Optimization

Priority: High

Status: Warm-cache fast path implemented. Current `v4` cold 25-product run is approximately 390 seconds; further tuning is limited to targeted failures and must preserve the accepted quality gate.

Objective:

- reduce uncached response time and keep repeated-request cost close to zero without weakening benchmark quality

Implementation tasks:

1. measure cold and warm runs separately for 1, 5, and 10 products
2. calculate model calls, web-search calls, prompt tokens, completion tokens, and estimated API cost per item
3. remove unnecessary narrative/detail generation where it does not affect classification or legal traceability
4. test reference parallelism values 2 and 3 under API rate limits
5. retain the lowest-cost configuration that passes the quality benchmark

Acceptance criteria:

- warm repeated requests are served primarily from cache
- no duplicate request causes duplicate paid processing
- normal 10-product batches complete without full per-item fallback
- manufacturer-reference runs use web search only for unresolved references
- a before/after table records cost, time, model calls, and quality metrics

Warm-cache implementation result:

- classification requests no longer block on the remote cache-disabled status check
- the status uses a 30-second in-process TTL and refreshes in a daemon thread when stale
- admin status reads still force a remote refresh, and successful admin updates refresh local state immediately
- valid full-request cache payloads bypass repeated legal normalization
- fully cached structured item sets bypass repeated RGI, completeness, position, and tariff enrichment
- fresh and partially cached requests continue to use the complete quality pipeline
- measured 10-item item-cache load: approximately 4.76 seconds
- measured cached merge and serialization: approximately 0.008 seconds
- previous cached merge/normalization stage took approximately 12.9 seconds
- expected warm 10-item endpoint duration after restart is approximately 5-7 seconds under similar Redis latency
- post-restart analysis identified an additional approximately 60-second CPU delay in assistant-meta fuzzy matching over structured product lists
- structured merchandise payloads now bypass that FAQ-only matcher while plain text assistant questions retain it
- final post-restart 10-reference verification completed in approximately 4.738 seconds
- the final warm run returned 10 of 10 cached items with zero OpenAI calls and zero tokens
- warm cached response time improved by approximately 93.9% versus the 77.66-second baseline

### Phase 4. Low-Confidence and Failure Handling

Priority: High

Objective:

- prevent uncertain internet identification or incomplete product information from appearing as a confident final result

Implementation tasks:

1. define confidence thresholds for confirmed, provisional, and unresolved identification
2. require source evidence for externally identified manufacturer references where available
3. stop or limit final-line classification when essential discriminating information is missing
4. show a clear frontend message describing the exact information needed from the user
5. ensure unresolved items do not prevent valid items in the same submission from completing

Acceptance criteria:

- uncertain references are visibly marked and not presented as guaranteed matches
- missing-information guidance is product-specific
- one failed item does not discard successful batch results
- logs explain whether failure occurred in identification, search, retrieval, classification, parsing, or storage

### Phase 5. End-to-End Regression and Release Validation

Priority: Critical

Objective:

- validate the full user journey before declaring the current scope complete

Test matrix:

1. manual single product with full details
2. manual manufacturer reference only
3. 10 normal products imported from CSV
4. 10 manufacturer references imported from CSV
5. repeated warm-cache runs
6. mixed valid, ambiguous, and invalid products
7. individual and bulk validation
8. admin history display and CSV export
9. backend restart followed by cache-reuse verification
10. frontend mobile and desktop checks for import, progress, results, and errors

Acceptance criteria:

- frontend and backend compile/type checks pass
- targeted backend unit and integration tests pass
- imported row count equals returned classification count
- validated records appear once in admin history
- no validation secrets or full sensitive payloads are written to normal production logs
- progress stream ends in a clear success, partial-success, or failure state
- implementation progress and client change documentation match the released code

## 10. Definition of Current-Scope Completion

The current scope will be considered complete when all of the following are true:

- manufacturer references trigger external identification when required
- repeat references reuse both identification and classification cache successfully
- normal and reference batches return one result per valid input
- quality benchmark shows no unacceptable regression from optimization
- low-confidence and unresolved products are clearly disclosed
- cost and duration are measured for cold and warm 1/5/10-item scenarios
- frontend import, progress, validation, storage, admin history, and export work end to end
- updated code and one final changes document are ready for client delivery

## 11. Execution Order

The remaining work should be completed in this order:

1. classification-cache diagnosis and fix
2. cache regression tests and repeated-run verification
3. quality benchmark and baseline scoring
4. benchmark-safe cost and latency tuning
5. low-confidence and failure UX hardening
6. complete end-to-end regression test
7. final changes document and client handover

This order protects the two client priorities: cost/time first, while using the quality benchmark as the release safety gate.

## 12. Current Completion Position

Implemented and verified in code:

- warm repeated 10-item requests return from item cache in approximately 4.4-4.8 seconds with zero OpenAI calls
- structured batches preserve one result per input and avoid whole-batch paid retries
- compact prompts and cheaper-model routing are active for fresh structured batches
- manufacturer references are imported, detected, externally identified when required, cached and surfaced in progress events
- CSV/Excel import, French/English header aliases and downloadable template are implemented
- frontend progress, validation, admin history and JSON/CSV result export are implemented
- quality gate currently has zero severe mismatches
- deleted ceramic heading `69.08` is migrated to current HS 2022 position `69.07`
- ceramic water-absorption bands are resolved deterministically to `6907.21/22/23`
- `v13/v8` quality hardening prevents unsupported single-child TEC lines from being shown as confirmed
- generic camera/tablet/display functional routing and conservative blank-code recovery are implemented without product-name mappings
- focused quality and cache regression suite passes; fresh live client-data verification remains the release gate

Final evidence completed for release sign-off:

1. post-restart 25-product benchmark returned 25/25 results
2. ceramic tile resolved to `6907.21.00.00` with only one targeted paid classification call
3. immediate warm rerun returned 25/25 item-cache hits and zero OpenAI calls
4. final benchmark measured 60 percent exact HS6, 100 percent heading and 100 percent chapter accuracy
5. final backend duration measured 66.884 seconds for the selective one-item refresh and 8.617 seconds fully warm
6. Python compile, frontend TypeScript and 63 focused backend tests passed

## 13. Deferred Scope

The following items remain outside the current completion plan unless separately approved:

- a complete manufacturer/part-number database
- guaranteed identification of every product available on the internet
- a complete deterministic CEDEAO/TEC legal decision-tree engine
- full Word/PDF invoice OCR and arbitrary document-layout extraction
- guaranteed official customs classification without declarant or customs-expert validation
- a fixed API price for every possible product and input type

## 14. Mission Realignment and Full Pipeline Re-evaluation

Date: 2026-07-22

### 14.1 Product mission

Mosam must accept a normal description or manufacturer/part reference, identify the actual
product, and produce a fast, traceable and defensible CEDEAO/TEC proposal. It must work on
previously unseen products and must not depend on brand/model-to-code mappings.

The seven client-reported products remain regression tests only. They are not the product
boundary and cannot be used as proof of general classification accuracy.

### 14.2 Current requirement assessment

| Client requirement | Current status | Evidence and gap |
|---|---|---|
| Faster responses | Partial | Warm cached requests reach roughly 4-9 seconds, but a fresh 7-product run took 269 seconds and a fresh 40-product run took 1,817 seconds. |
| Lower API cost | Partial | Repeated requests can use zero OpenAI calls, but the fresh 7-product run used 34,795 tokens and the fresh 40-product run used about 196,497 tokens. |
| Complete/correct codes | Partial | The seven reported headings now pass, but candidate recall is 4/7, false functional contradictions remain, and several results stop at heading/HS6 because legal criteria are missing. General accuracy is not proven. |
| Manufacturer/part references | Partial | Detection, web identification, source capture and caching exist. Accuracy on a broad unseen reference-only benchmark is not yet established, and retries can still be expensive. |
| Reliable file import | Mostly implemented for tabular import | CSV/XLS/XLSX/XLSM import works and PDF/DOCX extraction exists in the direct file-classification path. Large jobs are still in-process and not durable across restart/failure. |
| Stable multi-product processing | Partial | Row-count integrity, per-item cache and fallback recovery work. Fresh normal batches are sequential and therefore remain slow and expensive. |

### 14.3 Architectural mistakes identified

1. The official TEC is retrieved primarily as raw PDF chunks rather than as a clean
   chapter/heading/subheading/national-line hierarchy. Truncated or inherited labels can corrupt
   candidate scoring and functional checks.
2. The production setting `MOSAM_RAG_EXTRA_SEARCHES_ENABLED=false` disables broader functional
   retrieval. This reduces embedding cost but weakens unseen-product candidate recall.
3. The LLM is asked to choose a code before the deterministic legal stages run. RGI and
   subposition modules mostly validate, truncate or explain the hypothesis instead of driving
   the complete decision from candidates.
4. Candidate reranking and functional coherence rely heavily on lexical overlap across French
   and English. This creates unrelated alternatives and false contradictions.
5. Three-item prompts exceed the cheap-model routing threshold, so most fresh batches still use
   GPT-5 and produce large justifications and narratives.
6. Normal structured batches run sequentially. Only reference-only per-item mode currently has
   bounded parallel execution.
7. Any non-empty provisional classification can enter item cache. A weak first answer can
   therefore be reused as if it were a stable decision.
8. Manufacturer-reference cache keys can collapse to the reference alone and ignore stronger
   details supplied later by the user.
9. User-validated examples enter the similarity index without a separate customs-expert approval
   gate, creating a potential feedback-contamination risk.
10. Telemetry aggregates tokens by operation rather than model, so exact per-model cost cannot be
    calculated reliably.
11. Large file jobs run inside the API process and are not resumable, durable or independently
    retryable per item.

## 15. Revised General-Purpose Implementation Plan

### Phase A. Establish an independent quality baseline

Priority: Critical

1. Build a development benchmark of at least 100 products covering many TEC sections and product
   families.
2. Build a separate holdout benchmark that is never used while changing rules.
3. Include at least 30 manufacturer-reference-only cases, ambiguous cases, components, complete
   systems and products with missing discriminants.
4. Have expected chapter, heading and subheading labels reviewed by a customs-domain expert.
5. Score chapter accuracy, heading accuracy, HS6 accuracy, full TEC-line accuracy, blank-code rate,
   false-high-confidence rate, candidate recall, cost and latency separately.

Acceptance gate:

- no feature is accepted because it improves only the seven known products
- holdout heading recall and accuracy must not regress
- every result report distinguishes official expert labels from provisional internal labels

### Phase B. Rebuild the TEC knowledge layer as structured data

Priority: Critical

1. Parse the official nomenclature into explicit entities for section, chapter, heading,
   subheading and national TEC line.
2. Store full inherited labels, parent relationships, legal notes, units and rates without PDF
   chunk-boundary truncation.
3. Validate referential integrity: every child has a parent, codes are unique, and labels/rates
   match the source document.
4. Keep raw chunks only for explanatory notes; do not use them as the primary code catalogue.
5. Version the nomenclature and all indexes by source edition.

Acceptance gate:

- deterministic lookup returns the correct complete official label for every indexed code
- no mojibake/truncated heading is used for candidate affinity or coherence
- hierarchy traversal works from chapter to national line

### Phase C. Create a universal product-evidence stage

Priority: Critical

1. Produce a typed product-evidence object containing identity, function, technical nature,
   complete-system/component role, composition, specifications, manufacturer reference, source
   URLs and missing customs discriminants.
2. Use local parsing first for detailed descriptions.
3. For sparse references, perform one bounded web-identification pass with a cheap model and
   source evidence; escalate only when identity remains genuinely ambiguous.
4. Never accept a web-provided tariff code as evidence; web search identifies the product only.
5. Cache identity evidence separately from tariff decisions.

Acceptance gate:

- reference-only benchmark records correct identity/function and supporting sources
- uncertain identity is explicit and cannot produce a confirmed detailed tariff line
- repeated identity lookup uses cache without hiding newly supplied product evidence

### Phase D. Replace single-path RAG with hybrid candidate retrieval

Priority: Critical

1. Build lexical retrieval over structured official labels and notes.
2. Build semantic retrieval over complete heading/subheading records, not arbitrary page chunks.
3. Merge lexical, semantic, legal-note and validated-expert-example candidates.
4. Generate one query embedding per item and reuse it across retrieval stages.
5. Rerank candidates using the typed product evidence and complete official labels.
6. Keep manually authored product-family aliases out of the primary decision path; aliases may
   assist query normalization but must not map products to codes.

Acceptance gate:

- correct heading appears in top candidates for at least 95 percent of the expert holdout set
- candidate recall is measured before final LLM classification
- retrieval remains effective on product families absent from development examples

### Phase E. Make the decision process hierarchical and evidence-based

Priority: Critical

1. Select and eliminate chapters/headings using product evidence, official labels and legal notes.
2. Walk the structured hierarchy one level at a time.
3. Evaluate each TEC discriminant as confirmed, excluded or unverifiable.
4. Stop at the last legally supported level when evidence is missing.
5. Use a cheap structured-output model for candidate elimination when deterministic evidence is
   insufficient.
6. Reserve the stronger model for genuine close alternatives, not every normal batch.
7. Generate narrative and RGI trace locally from the final decision record instead of asking the
   LLM for a long report.
8. Track separate confidence values for product identity, candidate retrieval, heading decision
   and subheading decision.

Acceptance gate:

- no full code is confirmed when a required criterion is unverifiable
- false functional contradictions and unrelated alternatives fall below the agreed threshold
- every selected/rejected candidate has a traceable evidence reason

### Phase F. Redesign cache, cost and latency controls

Priority: High

1. Create cache keys from nomenclature version, pipeline version, normalized identity and a
   functional-evidence fingerprint.
2. Use long TTL only for high-quality stable decisions.
3. Use short TTL or no reusable decision cache for unresolved, contradictory or low-confidence
   results.
4. Keep commercial fields such as quantity/value/origin outside the reusable tariff decision.
5. Record token and duration totals per model and per stage.
6. Run safe item/batch work concurrently with bounded workers and rate-limit backoff.
7. Define realistic service levels separately:
   - warm/simple detailed item: a few seconds
   - fresh detailed item: target under 10-15 seconds
   - sparse reference requiring web evidence: target under 20-30 seconds
   - batch: progressive per-item completion rather than waiting for the entire list

Acceptance gate:

- exact cost can be calculated per request and per item
- no provisional contradiction is treated as a stable cached answer
- warm requests require zero paid classification calls
- cold latency is measured at p50 and p95, not from one sample

### Phase G. Make file and batch processing durable

Priority: High

1. Convert large imports into persistent jobs with one state per item.
2. Use a queue/worker model with bounded concurrency, retry and rate-limit handling.
3. Persist progress so jobs survive API restart and frontend disconnection.
4. Allow successful items to complete even when another item fails.
5. Provide per-item states: imported, identifying, retrieving, deciding, needs information,
   completed or failed.
6. Reuse the same classification pipeline for manual, imported and reference-only items.

Acceptance gate:

- submitted item count equals completed plus explicitly failed/unresolved item count
- a restart does not lose the job
- retries do not duplicate paid work or stored history

### Phase H. Release validation

Priority: Critical

1. Run development, holdout and client regression suites.
2. Test cold and warm 1/5/10/40-item scenarios.
3. Test detailed products, sparse references, ambiguous references and mixed batches.
4. Verify import, progress, result trace, validation, storage, admin history and exports.
5. Publish a before/after matrix for quality, cost, latency and failure rate.

Release gate:

- the seven client cases still pass, but release approval is based on the unseen holdout
- candidate recall, heading accuracy, false-confidence rate, cold/warm latency and cost meet the
  agreed thresholds
- documentation describes limitations honestly and does not promise guaranteed official customs
  classification

## 16. Revised Execution Order

1. Freeze new product-family patches except critical safety regressions.
2. Build the expert-reviewed development and holdout benchmark.
3. Rebuild and validate the structured TEC hierarchy.
4. Implement hybrid candidate retrieval and measure candidate recall.
5. Implement the typed evidence object and reference-identification policy.
6. Move classification to hierarchical evidence-based decisions.
7. Compact/localize report generation and route models by uncertainty.
8. Redesign quality-aware cache and per-model cost telemetry.
9. Add durable batch jobs and item-level progress.
10. Run release validation and prepare the final client change document.

This order restores the real product mission: general classification of new goods with defensible
uncertainty, rather than accumulating fixes for products already seen during development.

### Implementation status after first general-purpose increment

Date: 2026-07-22

| Workstream | Status | Current result |
|---|---|---|
| Independent benchmark contract | In progress | Release gate, split/input metadata, candidate recall and false-confidence metrics implemented; expert-reviewed 100+ dataset still required. |
| Structured TEC hierarchy | Foundation complete | 18,450 linked nodes built from 6,009 official labels with zero invalid codes and zero orphans. |
| Hybrid candidate retrieval | In progress | Zero-cost structured lexical retrieval added alongside existing semantic FAISS retrieval. |
| Product evidence | Capability increment complete | Unified evidence now includes locally derived generic technical nature, confidence and matched signals without brand/model/code mappings. |
| Hierarchical legal decision | In progress | Chapter-first candidate ranking and confidence guards are active; deterministic heading/subheading traversal still needs completion. |
| Universal cache policy | In progress | Product-specific cache versions removed and functional-evidence-aware reference keys added; quality-based TTL remains. |
| Durable batch jobs | Pending | Existing in-process batch path remains. |
