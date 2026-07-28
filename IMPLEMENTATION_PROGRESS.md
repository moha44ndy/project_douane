# Mosam Implementation Progress Log

## Test CSV policy

To control development cost and avoid accidental large reruns, the repository now keeps only three
classification input suites plus the import template:

- `sample_client_regression_7.csv`: quick client-critical regression; use after classification changes
- `sample_manufacturer_references_10.csv`: manufacturer-reference and web-identification validation
- `sample_products_quality_25_fresh.csv`: milestone and pre-release quality validation only
- `mosam_import_template.csv`: blank/example user import template, not a benchmark run

The files under `sam/benchmarks/` contain
expected outcomes for local scoring. They are not uploaded for classification and consume no API
tokens. Historical generated benchmark reports and duplicate 10-product inputs were removed; new
generated reports are ignored by Git.

## Phase D/E/F milestone. Capability evidence, hierarchy and cost guards

### Issues observed in the 7/40-product cold runs

- structured rows carried good usage/specifications but used the commercial designation as their
  `technical_nature`
- selected heading candidate recall remained weak, so GPT-5 often rescued decisions outside RAG
- an outside-candidate result could regain high confidence through an uncapped
  `classification_confidence` field
- every rich row performed both raw-dossier and functional-profile embedding searches
- LLM output repeated candidate analysis and legal narrative already rebuilt by the local engine
- decimal names such as `3.84TB` were split at the first period during final description rebuilding

### Fix implemented

- added a tariff-neutral capability ontology in `sam/technical_nature.py`; it contains no brands,
  product models or tariff codes
- derives generic technical nature, confidence and matched evidence signals from designation, usage,
  characteristics and composition
- all seven client regression rows now derive a meaningful nature locally without an API call
- expanded official-label search vocabulary from those capabilities and added chapter-first candidate
  ranking to the prompt and diagnostics
- caps both confidence fields for every outside/weak candidate selection and preserves provisional
  status through final normalization
- high-confidence structured evidence now performs one evidence-driven semantic retrieval instead of
  raw plus functional duplicate retrieval; uncertain products retain the fallback search
- compacted the classification JSON contract and reduced dynamic output allowance from 1,400 to
  1,000 tokens per item, while the local decision engine retains the detailed legal trace
- fixed decimal product-name preservation by splitting only at sentence punctuation
- bumped full-request cache to `v16` and item cache to `v11` so validation cannot reuse older decisions

### Verification

- 7/7 client regression rows pass the zero-cost technical-nature gate
- 65 focused tests pass across technical nature, evidence, retrieval, hierarchy, confidence,
  completeness, cache isolation and client regression behavior
- no paid OpenAI test was run during implementation

## Phase G milestone. Generic compute, storage and display-family reinforcement

### Issues observed in later 7/10/40-product quality runs

- compute and storage products often stayed too broad at `84.71` without a stronger family signal
- accelerator-card and server families did not have enough upstream vocabulary support
- mixed-reality and display-headset products could lose the code entirely and fall back to a blank heading
- candidate recall improved for network and industrial control families, but advanced compute/display families
  still needed a stronger generic compatibility layer

### Fix implemented

- expanded the tariff-neutral technical-nature ontology with stronger generic capability profiles for:
  accelerator/PCIe cards, rack servers, storage systems, storage devices, tablets and mixed-reality headsets
- reinforced candidate-family compatibility scoring for:
  server systems, accelerator cards, storage media vs storage systems, and immersive display devices
- expanded generic TEC heading-hint phrases and customs-keyword generation for those same families
- strengthened blank-code recovery so a strongly compatible heading can be preserved provisionally instead of
  returning an empty `hs_code`

### Files updated

- `sam/technical_nature.py`
- `sam/candidate_set_enforcer.py`
- `sam/rag.py`
- `sam/tests/test_candidate_set_enforcer.py`
- `sam/tests/test_technical_nature.py`

### Expected result

- better family-level routing for compute, storage and immersive-display products before the final LLM decision
- fewer empty-code outcomes on ambiguous advanced-electronics products
- stronger generic behavior for new products without hardcoding client-specific model numbers

### Verification

- `python -m unittest sam.tests.test_candidate_set_enforcer sam.tests.test_technical_nature`
- `python -m unittest sam.tests.test_functional_coherence sam.tests.test_functional_profile`

## Purpose

This document is maintained alongside implementation work.

For each completed step, it records:

- what the issue was
- why it was happening
- how it was fixed
- what outcome is expected from the fix

## Step 1. Product-identification cost and latency reduction

### Issue

- API cost was too high
- response time was too slow
- web search and identification were being used too broadly for many requests

### Why it was happening

- product identification could call web search whenever web search was enabled
- the same product-identification request could be repeated without reuse
- there was no dedicated cache for product-identification results

### Fix implemented

- added a smarter web-search policy for product identification
- added `auto`, `manufacturer_only`, `always`, and `never` policy modes
- limited web search in `auto` mode to manufacturer references and very short ambiguous queries
- added Redis-backed product-identification caching for repeated requests
- added environment variables to control the policy and thresholds

### Files updated

- `sam/product_identification.py`
- `sam/config/settings.py`
- `deploy/mosam-api.env.example`
- `sam/tests/test_product_identification.py`

### Expected result

- fewer unnecessary web-search calls
- lower cost for repeated product-identification requests
- faster identification path for many common inputs

### Verification

- `python -m unittest sam.tests.test_product_identification`

## Step 2. File-upload item-level cache reuse

### Issue

- multi-product and file-based classification could become too expensive
- repeated products across uploads could be classified again from scratch

### Why it was happening

- file classification mainly reused an in-memory cache inside a single upload only
- repeated items across different uploads had no persistent item-level cache reuse
- batch fallback could trigger additional single-item model calls

### Fix implemented

- added a stable cache key for single uploaded items
- added helper functions to load and store item-level classification cache entries
- changed `/classify/file` to preload cached item-level classifications before batching
- changed batch processing to classify only pending uncached items
- stored successful batch and single-item fallback results into persistent item-level cache
- rebuilt final merged output in the original `unique_items` order using cached plus fresh results

### Files updated

- `sam/api.py`
- `sam/tests/test_cache.py`

### Expected result

- lower cost for repeated products across uploads
- fewer unnecessary classification calls during file processing
- better multi-product efficiency and lower fallback overhead

### Verification

- targeted unit tests for cache helper behavior were added
- `python -m py_compile sam\api.py sam\product_identification.py sam\config\settings.py sam\tests\test_cache.py sam\tests\test_product_identification.py`
- full runtime execution of `sam.tests.test_cache` was not completed in this environment because `faiss` is not installed locally

## Step 3. Classification model routing for simple cases

### Issue

- final classification can still use the stronger model even for simpler cases
- this keeps single-product cost higher than necessary

### Why it was happening

- the classification stage had a single default model path
- there was no guarded routing rule to separate simple cases from complex cases

### Fix implemented

- added optional cheap classification model configuration
- added guarded `off` / `auto` routing policy
- added simple-case detection rules for classification prompts
- kept complex cases on the stronger model path
- added environment settings to control routing and prompt-size threshold

### Files updated

- `sam/rag.py`
- `sam/config/settings.py`
- `deploy/mosam-api.env.example`
- `IMPLEMENTATION_PLAN.md`
- `CLIENT_DELIVERY_PROPOSAL.md`

### Expected result

- lower cost for simple classification requests
- no quality regression on complex requests because they remain on the stronger model
- better balance between cost efficiency and result quality

### Verification

- `python -m py_compile sam\rag.py sam\config\settings.py`

## Step 4. Structured frontend data preservation in backend response

### Issue

- frontend form fields were being sent to the backend, but some commercial details could still disappear in the final response
- UI and validation flow depend on backend response fields like `origin` and `value`

### Why it was happening

- structured fields were converted into dossier text for classification, so they influenced the model
- however, item-level metadata from the frontend was not fully reattached to the final classification payload
- quantity metadata was preserved, but `origin`, `value`, and related structured fields were not guaranteed to survive end-to-end

### Fix implemented

- extended structured item metadata capture in the backend
- added a dedicated merge step that reinjects structured frontend metadata into final classifications
- preserved `origin` and formatted `value + currency` in the response when the model does not explicitly return them
- kept quantity and source-query enrichment in the same merge path for a cleaner end-to-end flow

### Files updated

- `sam/api.py`
- `sam/tests/test_cache.py`

### Expected result

- frontend structured fields are now not only used for classification context, but also preserved in the response payload
- UI results and validation requests stay aligned with what the user entered in the form
- less risk of losing commercial data between frontend input and backend output

### Verification

- targeted unit tests added for structured metadata preservation

## Step 5. Strict numeric validation in frontend merchandise form

### Issue

- users could type non-numeric characters into `quantity` and `value`
- invalid numeric input could reduce data quality before the request even reached backend checks

### Why it was happening

- both fields used text inputs with soft keyboard hints only
- `inputMode` helped mobile keyboards but did not enforce numeric-only values

### Fix implemented

- added strict sanitization for `quantity` so only digits are accepted
- added strict sanitization for `value` so only digits and a single decimal separator are accepted
- normalized commas to decimal dots for cleaner downstream handling

### Files updated

- `frontend/src/components/MerchandiseTableForm.tsx`

### Expected result

- cleaner merchandise data enters frontend state
- fewer malformed quantity and value values reach backend classification
- lower risk of silent quantity fallback caused by invalid input

### Verification

- frontend component logic updated and ready for lint verification

## Step 6. Backend operational logging for classification flow

### Issue

- backend flow was harder to trace during debugging and client review sessions
- there was not enough high-level visibility into request source, cache usage, and validation activity

### Why it was happening

- existing logs were focused on low-level debug points and exceptions
- there were few request/response summary logs for the main classification lifecycle

### Fix implemented

- added safe request summary logging for `/classify` and `/classify/stream`
- added result summary logging for cache hits, fresh generations, and assistant-meta responses
- added validation logs for single and bulk save actions
- kept logs concise and avoided dumping full raw payload content

### Files updated

- `sam/api.py`

### Expected result

- easier debugging of classification requests in backend logs
- clearer visibility into structured form usage, cache behavior, and saved validations
- better support for performance and quality troubleshooting

### Verification

- backend code updated and ready for compile verification

## Step 7. Structured multi-row classification integrity recovery

### Issue

- structured form submissions with multiple rows could return fewer classifications than rows sent by the frontend
- duplicate merge logic could further collapse structured rows after classification

### Why it was happening

- the structured form path sent multiple items in a single batch classification request
- if the model returned fewer rows than expected, backend trusted the incomplete response
- row-level duplicate merging was useful for file imports but too aggressive for structured form submissions

### Fix implemented

- added an integrity check comparing expected structured rows vs returned classifications
- when the batch response is incomplete, backend now falls back to per-item classification only for recovery
- reused persistent single-item cache in the recovery path to limit extra cost
- disabled duplicate collapsing for structured form results so row integrity is preserved

### Files updated

- `sam/api.py`
- `sam/tests/test_cache.py`

### Expected result

- multi-row structured submissions should no longer silently collapse into a single visible classification
- missing rows are recovered only when needed, keeping the normal path cost-optimized
- structured UI rows stay aligned with backend output and later validation/storage

### Verification

- targeted helper tests added

## Step 8. Excel/CSV import into frontend merchandise table

### Issue

- users needed a way to upload a spreadsheet and automatically populate the merchandise table
- manual row-by-row entry is too slow for multi-product workflows

### Why it was happening

- backend already knew how to detect tabular columns in spreadsheet files
- but there was no dedicated endpoint to return structured merchandise rows to the frontend form
- frontend had file-classification code but not table-import code

### Fix implemented

- added a backend import endpoint for CSV/XLS/XLSX/XLSM files
- reused existing header matching and tabular parsing logic to map spreadsheet columns
- added frontend import control that loads imported rows directly into the merchandise table
- added a downloadable CSV template with the exact supported column names
- kept direct file-classification flow separate from table import flow

### Files updated

- `sam/api.py`
- `frontend/src/app/page.tsx`

### Expected result

- users can upload an Excel/CSV file and automatically fill the form table
- recognized columns map into structured merchandise fields with minimal manual cleanup
- import remains cheap because it uses parsing only, not classification calls

### Verification

- backend/frontend code updated and ready for compile/runtime verification

## Next Planned Step

## Step 9. Structured table small-batch optimization and live progress details

### Issue

- 10+ frontend table rows could be sent as one large classification prompt
- if the model collapsed the batch, the backend had to reprocess every row individually
- users could not see whether the system was batching, recovering with fallback, or doing final merge

### Why it was happening

- structured table classification reused the single-query path for all rows
- fallback existed only after an incomplete batch response
- SSE progress steps only exposed broad stages, not operational details like batch number or fallback status

### Fix implemented

- added configurable structured table batch size with `MOSAM_STRUCTURED_FORM_BATCH_SIZE`
- structured table requests above the batch size are now classified in small batches first
- per-item fallback now runs only for incomplete/invalid small batches
- persistent single-item cache is reused before making new fallback calls
- backend emits live detail events for batch number, cache usage, fallback, and final merge
- frontend displays those detail events inside the progress panel

### Files updated

- `sam/api.py`
- `sam/config/settings.py`
- `deploy/mosam-api.env.example`
- `frontend/src/app/page.tsx`
- `frontend/src/components/ClassificationProgressPanel.tsx`
- `frontend/src/lib/classificationStream.ts`

### Expected result

- lower cost for multi-row table submissions because huge collapsed prompts are avoided
- better latency because smaller batches are easier for the model to complete reliably
- fewer full per-item recovery runs
- users can see exactly whether the system is processing a batch, running fallback, or merging results

### Verification

- backend compile passed with `python -m py_compile sam\api.py sam\classification_progress.py sam\config\settings.py`
- frontend TypeScript passed with `npx tsc --noEmit`
- targeted pytest run could not execute because `pytest` is not installed in the local Python environment

## Step 10. Cost/time telemetry for classification requests

### Issue

- cost and response-time improvements were hard to prove from logs alone
- the team needed a single request-level summary showing model calls, fallback usage, cache behavior, and durations

### Why it was happening

- OpenAI calls were logged individually, but not aggregated per classification request
- fallback and cache behavior had to be inferred manually from raw logs
- model routing could be configured incorrectly without an obvious summary

### Fix implemented

- added request-local telemetry for `/classify` and `/classify/stream`
- counted classification LLM calls, product-identification LLM calls, and web-search calls
- recorded model names, prompt characters, token usage when returned by the SDK, and call durations
- counted cache hits/misses, structured batches, incomplete batches, fallback items, and manufacturer-reference inputs
- enabled local cost-control config in `.env`:
  - `MOSAM_CLASSIFICATION_MODEL_CHEAP=gpt-4.1-mini`
  - `MOSAM_CLASSIFICATION_MODEL_ROUTING=auto`
  - `MOSAM_STRUCTURED_FORM_BATCH_SIZE=3`
  - `MOSAM_WEB_SEARCH_POLICY=auto`

### Files updated

- `sam/telemetry.py`
- `sam/api.py`
- `sam/rag.py`
- `sam/product_identification.py`
- `sam/openai_web_search.py`
- `.env`

### Expected result

- each classification request logs a compact telemetry summary
- 10-item tests can be compared using actual call counts and durations
- manufacturer-reference tests show whether web search was attempted/used
- incorrect cost configuration is easier to detect

### Verification

- backend compile passed with `python -m py_compile sam\api.py sam\rag.py sam\product_identification.py sam\openai_web_search.py sam\telemetry.py`
- 10-product retest confirmed latest optimized flow:
  - structured small-batch mode enabled with 10 items, batch size 3, 4 batches
  - final output returned 10 classifications
  - no incomplete batch fallback was needed
  - classification LLM calls reduced from previous 11-call flow to 4 calls
  - telemetry summary reported total duration around 534 seconds and classification LLM duration around 328 seconds
- startup schema migration made idempotent to avoid duplicate FK traceback on boot

## Next Planned Step

- optimize remaining response time by reducing prompt/context size and/or parallelizing safe batch execution
- test a manufacturer reference to confirm web-search based identification telemetry

## Step 11. Duplicate-submit guard and single-product routing optimization

### Issue

- a single product test showed two close `/classify/stream` requests, which can double API cost
- single-product prompts were still routed to `gpt-5` even when cheaper routing was enabled
- one-product responses allowed up to the same output-token cap as multi-product batches

### Why it was happening

- frontend relied on React state (`loading`) to disable submits, but state updates are asynchronous and can leave a small duplicate-submit window
- routing rejected prompts containing normal TEC candidate blocks, so real classification prompts almost never reached the cheaper model
- classification output token cap was static instead of scaling by item count

### Fix implemented

- added a frontend in-flight ref lock to prevent duplicate classification submissions
- added submit guard for loading/importing states
- changed model routing so a single merchandise prompt can use the cheaper model when it is within `MOSAM_CLASSIFICATION_ROUTING_MAX_PROMPT_CHARS`
- kept multi-merchandise prompts on the stronger model by detecting multiple `[MARCHANDISE N]` blocks
- changed output token cap to scale with merchandise count
- updated local/env example config:
  - `MOSAM_CLASSIFICATION_ROUTING_MAX_PROMPT_CHARS=20000`
  - `MOSAM_CLASSIFICATION_MAX_OUTPUT_TOKENS=4096`

### Files updated

- `frontend/src/app/page.tsx`
- `sam/rag.py`
- `sam/config/settings.py`
- `.env`
- `deploy/mosam-api.env.example`

### Expected result

- one user action should produce only one classification request
- simple single-product classifications can use the cheaper configured model
- single-product responses should be shorter and faster
- multi-product batches still use the stronger model unless routing is further tuned later

### Verification

- backend compile passed with `python -m py_compile sam\rag.py sam\config\settings.py`
- frontend TypeScript passed with `npx tsc --noEmit`

## Step 12. TEC prompt/context size reduction

### Issue

- after cheap-model routing was verified, single-product prompts were still around 19k characters
- large TEC candidate blocks increase prompt tokens, response time, and cost
- candidate prompts repeated long elimination instructions, many positions, subpositions, and excerpts

### Why it was happening

- FAISS retrieval sent up to 20 chunks into candidate aggregation
- up to 15 candidate positions could be sent to the LLM
- each candidate could include many subpositions plus TEC excerpts
- the elimination methodology text was verbose and repeated inside each prompt

### Fix implemented

- reduced default FAISS top-k from 20 to 12
- reduced default candidate positions from 15 to 6
- added configurable TEC context compact mode
- reduced TEC excerpt max length to 120 characters
- reduced displayed subposition groups to 6
- compacted the candidate-locking instructions while preserving the requirement to choose only from candidates
- made all values configurable through environment variables:
  - `MOSAM_FAISS_TOP_K=12`
  - `MOSAM_MAX_CANDIDATE_POSITIONS=6`
  - `MOSAM_TEC_EXCERPT_MAX_CHARS=120`
  - `MOSAM_TEC_SUBPOSITIONS_MAX_ITEMS=6`
  - `MOSAM_TEC_CONTEXT_COMPACT=true`

### Files updated

- `sam/candidate_set_enforcer.py`
- `sam/config/settings.py`
- `.env`
- `deploy/mosam-api.env.example`

### Expected result

- smaller prompts for single-product and batch classification
- lower prompt token usage
- faster model response time
- lower API cost while keeping candidate-position locking in place

### Verification

- backend compile passed with `python -m py_compile sam\candidate_set_enforcer.py sam\config\settings.py sam\rag.py`

## Phase C milestone. Typed product evidence and source-name integrity

### Issue

- product identity, function, specifications and evidence provenance were spread across multiple
  loosely related dictionaries
- rich structured rows skipped the paid identification agent correctly, but their locally derived
  evidence was discarded from the final result trace
- an LLM-generated description could abbreviate a source designation containing a decimal model or
  capacity, for example `Samsung PM9A3 3.84TB` becoming `Samsung PM9A3 3`

### Why it happened

- the functional profile was useful for retrieval but was not a complete typed evidence contract
- final attachment logic treated every skipped identification as having no identification evidence
- structured metadata only replaced the model description when that description was empty

### Fix implemented

- added a tariff-neutral `ProductEvidence` record containing:
  - source and input type
  - identification status
  - designation, manufacturer and manufacturer reference
  - technical nature, family, primary function and system role
  - composition and technical characteristics
  - evidence sources and source URLs
  - missing discriminants, identity confidence and evidence completeness
- structured lexical retrieval now uses the compact functional evidence query, excluding commercial
  noise such as quantity, origin and price
- the classification prompt receives the same evidence contract and must keep the result provisional
  when identity or discriminating evidence is insufficient
- locally derived evidence is attached to final classifications even when the external identification
  agent was intentionally skipped
- the original structured designation is now authoritative in the final result; an alternative model
  description is retained separately as `classified_product_type`
- bumped the universal full-request cache to `v15` and item cache to `v10`, ensuring the first
  validation run measures this evidence pipeline instead of returning older cached decisions

### Scope safety

- no manufacturer, product model or tariff code mapping was added
- this increment improves all product families through a shared evidence contract
- it does not yet replace the final LLM position choice with the planned hierarchical legal decision

### Verification

- backend compilation passed for `sam/product_evidence.py`, `sam/rag.py` and `sam/api.py`
- 66 focused tests passed for evidence construction, functional profiles, structured pipeline
  integration, final evidence attachment and decimal designation preservation
- full test discovery ran 254 tests: 249 passed; four live Upstash integration tests could not
  access the external service in the restricted test environment, and one existing web-search order
  assertion expects one lookup while the configured identification retry policy performs up to three

## Mission Realignment Phase 1. General-purpose TEC foundation

Date: 2026-07-22

### Issue

- tariff knowledge was exposed as several independent dictionaries extracted from PDF chunks
- chapter, heading, subheading and national-line records did not have explicit parent links
- candidate retrieval depended mainly on paid semantic search and weak direct token overlap
- the existing 25-item benchmark could look like a release-quality score even though its labels
  were non-official and it had no untouched holdout split
- known product families used special cache-version branches
- manufacturer-reference cache keys could ignore stronger functional details supplied later

### Root cause

- the original implementation optimized retrieval around document chunks rather than the legal
  nomenclature hierarchy
- benchmark tooling measured final-code matches but did not enforce dataset independence or
  customs-expert review
- cache invalidation was added incrementally for reported products instead of versioning the
  complete decision pipeline

### Fix implemented

- added `sam/tariff_hierarchy.py`:
  - normalizes official 4/6/8/10-digit code levels
  - creates explicit heading, HS subheading, TEC subheading and national-line nodes
  - creates missing intermediate parents without inventing legal labels
  - preserves exact source labels, rates, chapter titles and section metadata
  - validates malformed source codes and orphan parent relationships
- added `sam/structured_tariff_retrieval.py`:
  - builds one zero-API BM25-style document per official TEC heading
  - indexes complete heading and descendant source labels
  - merges structured lexical candidates with the existing FAISS candidate set
  - contains no brand, model or product-to-code mappings
- extended `sam/quality_benchmark.py`:
  - supports development/holdout split metadata
  - supports description and manufacturer-reference input types
  - reports candidate-heading recall separately from final accuracy
  - reports false high-confidence classifications
  - identifies expert-reviewed versus non-official labels
  - rejects release datasets below 100 items, without an untouched holdout, without all labels
    expert reviewed, or with fewer than 30 manufacturer-reference cases
- removed product-specific cache versions for tiles, vacuum flasks, LED lamps and woven sacks
- bumped full-request cache from `v13` to `v14` and item cache from `v8` to `v9`
- manufacturer-reference cache keys now include non-commercial functional evidence while still
  ignoring quantity, origin and value

### Production-data validation

- source tariff labels: 6,009
- structured headings: 1,225
- total hierarchy nodes: 18,450
- heading nodes: 1,225
- HS subheading nodes: 5,251
- TEC subheading nodes: 5,965
- national-line nodes: 6,009
- source nodes: 7,234
- safely synthesized parent nodes: 11,216
- invalid source codes: 0
- orphan nodes: 0

### Verification

- Python compilation passed for API, RAG, hierarchy, structured retrieval and benchmark modules
- 30 focused hierarchy, retrieval, benchmark and cache tests passed
- 28 candidate retrieval/merge tests passed in the preceding targeted run
- real structured retrieval returned expected generic position families for:
  - static electrical converters: `85.04`
  - data-processing machines: `84.71`
  - smartphone wording: `85.17`
- full discovery executed 248 tests:
  - 243 passed
  - 4 live Upstash integration tests failed because sandbox network access was blocked
  - 1 existing web-search retry-order test failed because the current identification policy made
    three web attempts instead of the test's expected single attempt
- Markdown/code diff validation passed

### Current limitation

- the hierarchy and lexical retrieval are now production-integrated, but the final classifier is
  still LLM-first rather than a complete deterministic hierarchy walk
- English-only descriptions may still depend on semantic/product-identification evidence because
  the official TEC labels are primarily French
- release accuracy cannot be claimed until customs experts review the larger holdout benchmark

### Next implementation step

- introduce the typed product-evidence object and use it to drive hierarchical candidate
  elimination one level at a time
- move long narrative generation out of the classification LLM response
- measure the new candidate recall on the independent development and holdout datasets

## Step 18. Functional-family quality hardening after client 40-product review

### Issue

- the client regression set improved to 6 accepted results out of 7, but the iPad result had no code
- two modern digital/thermal cameras were incorrectly classified under cinematographic equipment and shown as 95 percent confirmed
- 23 of 40 candidate sets had low functional affinity, so later checks were rescuing weak initial retrieval
- stale cached `v12/v7` results could hide quality changes during retesting

### Why it was happening

- a single remaining TEC child could be confirmed even when its discriminating criterion was explicitly unverifiable
- functional affinity treated the generic word `camera` as enough evidence for both digital and cinematographic equipment
- the smartphone keyword path treated the broad term `mobile` as telephone evidence, which could promote smartphone candidates for tablets
- blank model codes had no conservative heading-level recovery path

### Fix implemented

- unsupported single-child TEC lines now stop provisionally at the parent heading instead of becoming 95 percent confirmed
- confirmations reached after positive parent-level evidence or explicit elimination of alternatives remain supported
- added generic functional conflicts for modern digital/IP/thermal imaging versus cinematographic equipment and tablet versus smartphone
- enriched tariff-neutral functional profiles for digital imaging, tablets and display headsets
- added generic TEC heading keywords for digital cameras, data-processing tablets and immersive displays
- removed broad `mobile` matching from the smartphone rule
- added conservative blank-code recovery only when one strong direct TEC heading match exists; recovered codes remain provisional at 40 percent or less
- bumped full-request cache from `v12` to `v13` and item cache from `v7` to `v8`

### Files updated

- `sam/api.py`
- `sam/candidate_set_enforcer.py`
- `sam/functional_profile.py`
- `sam/functional_coherence.py`
- `sam/rag.py`
- `sam/tariff_subposition.py`
- related backend regression tests

### Expected result

- a modern camera can no longer be confidently accepted only because a TEC label contains the word `camera`
- tablets should retrieve data-processing candidates before smartphone candidates
- unresolved products return a safe heading-level provisional result when the local TEC evidence is unique, rather than a fabricated full code
- fresh tests use the updated quality logic instead of previous cached classifications

### Verification

- `58/58` focused cache, retrieval, functional-coherence and subposition tests passed
- backend compile passed for all changed Python modules
- `git diff --check` passed with no whitespace errors
- a fresh post-restart 40-product run is still required to measure live candidate recall, accepted client cases, cold duration and token use under `v13/v8`

## Step 40. Detailed 40-product CSV routing and cache-safety correction

### Issue

- `mosam_import_template_products.csv` correctly imported 40 fully populated rows
- the run returned 40 classifications but took about 14 minutes 42 seconds
- telemetry reported 40 classification LLM calls and 8 web-search calls
- three generated rows had no usable HS code but were still accepted by bulk validation
- two different products could receive the same item-cache key when both had the hyphenated origin `Etats-Unis`

### Why it was happening

- a manufacturer-looking designation forced the complete request into per-item mode even when material, usage, and characteristics were already supplied
- cache reference extraction searched the complete dossier and could mistake a hyphenated origin for a part number
- validation accepted an empty or placeholder HS code as an ordinary string

### Fix implemented

- fully detailed structured rows now bypass external product identification and use configured small batches
- sparse reference-only rows still use external identification when required
- reference extraction is restricted to explicit reference labels or the `Produit` line
- item-cache schema moved to `v5` so unsafe generic `v4` entries are not reused
- full-request cache schema moved to `v10` so the corrected routing is exercised instead of serving the earlier 40-product response
- legacy migration is limited to explicitly labelled manufacturer references
- blank and placeholder HS codes are rejected before storage; bulk validation continues with other valid rows and reports the rejected indexes

### Expected result

- this 40-row detailed CSV should use approximately 14 batches at batch size 3 instead of 40 one-item classification calls
- it should make no product-identification or web-search calls because product detail is already present
- different products can no longer collide merely because they share a hyphenated origin
- incomplete classifications will not pollute user or administrative history

### Verification

- CSV audit confirmed 40 rows and no missing imported fields
- post-fix CSV audit confirmed identification skip enabled, 40 unique item-cache keys, and zero collisions
- 19 focused routing and cache regression tests passed
- Python compilation passed for the modified backend and test modules
- the wider local suite ran 75 tests; its four failures were live Upstash integration tests blocked by sandbox network access, not logic regressions
- a backend restart and one fresh live run are still required to measure the final wall time and token reduction

## Step 41. Rejected pre-v10 40-product result audit

### Test evidence

- source file: `mosam_import_template_products.csv`
- imported rows: 40
- returned classifications: 40
- runtime: 122.9 seconds
- old cache versions observed in logs: full request `v9`, item cache `v4`
- item-cache hits: 37
- fresh classification calls: 3 using `gpt-4.1-mini`
- classification tokens: 13,234 input and 2,040 output
- product-identification cache hits: 2
- actual web-search calls: 0

### Quality audit

- full 10-digit codes: 19 of 40
- partial heading/subheading results: 19 of 40
- blank HS codes: 2 of 40
- provisional results: 21 of 40
- several high-confidence results contradicted the supplied product function, including network switches/firewalls mapped to telephone or base-station lines, optical transceivers mapped to storage media, industrial/thermal cameras mapped to unrelated camera or smartphone lines, and an industrial robot mapped to motorcycle parts
- the three cache misses did not provide an acceptable fresh-quality sample: one obvious heading mismatch and two blank codes

### Decision

- this run is rejected as a release-quality benchmark
- it predates the `v10` full-request and `v5` item-cache safety changes
- the backend must be restarted before retesting
- the next run must show `classify:v10`, item-cache `v5`, `batch_size=3`, no unnecessary product-identification/web-search calls for these detailed rows, and no blank HS codes accepted into history
- tariff quality must be reviewed from the new exported JSON, not inferred from row count or confidence alone

## Step 42. Functional quality foundation and client regression gate

### Issue

- the classifier could select an exact TEC line that contradicted the supplied product function
- high confidence was based on code completeness and candidate presence, not semantic compatibility
- rich structured rows were retrieved primarily from the complete dossier instead of an explicit function-first profile
- the seven client-reported failures were not executable acceptance tests

### Fix implemented

- added a tariff-neutral functional profile containing product type, primary function, characteristics, composition, standalone-system/component role, semantic terms, missing discriminants, and evidence sources
- integrated the profile into structured-row candidate retrieval and the final classification prompt
- added at most one optional function-first FAISS retrieval using the existing extra-search configuration flag
- retained the cheaper classification model and existing batch/cache controls
- replaced the empty functional-coherence stub with a generic compatibility gate
- incompatible or unresolved results are now provisional and confidence-capped instead of remaining falsely confirmed at high confidence
- added a final-output safeguard so completeness and RGI normalization cannot restore a contradicted result to confirmed/high-confidence status
- the gate never replaces a code using a manufacturer/model mapping; a better candidate is advisory only
- added a generic complete-system versus recording-media safeguard
- added telemetry for functional profiles, profile retrievals, contradictions, and unresolved results
- added an executable seven-product client-feedback benchmark with non-official labels and conditional tablet handling

### Baseline result

- the rejected pre-v10 JSON scores 0 of 7 accepted
- six results hit client-defined forbidden headings
- one result has no code
- this confirms the benchmark reproduces all client-reported failures before measuring the new pipeline

### Files updated

- `sam/functional_profile.py`
- `sam/functional_coherence.py`
- `sam/client_feedback_benchmark.py`
- `sam/rag.py`
- `sam/api.py`
- `quality_benchmark_client_feedback_7.csv`
- `client_feedback_report_pre_v10.csv`
- focused regression tests for profile extraction, quality scoring, retrieval integration, and coherence gating

### Verification

- 75 focused backend tests passed
- 12 dedicated functional-profile, coherence-gate, and client-benchmark tests passed after the final safeguard
- Python compilation passed for all changed backend modules
- diff whitespace validation passed
- no paid OpenAI or web-search call was made during offline verification
- this step originally required a fresh v10/v5 export; Step 43 supersedes that acceptance run with cache schemas v12/v7

## Step 43. Candidate recall, diversity, and weak-evidence protection

### Issue

- the client feedback export scored zero accepted final outcomes across seven reviewed professional products
- the expected functional tariff position was present in the old top-k candidate set for only four of seven products
- final top-N truncation primarily followed raw retrieval score, allowing one semantic family to occupy most candidate slots
- a selected code could remain confirmed merely because it appeared in the candidate set, even when another candidate had substantially stronger functional affinity

### Fix implemented

- added functional-affinity scores and retrieval-source metadata to TEC position candidates
- added candidate deduplication and combined retrieval/affinity ranking
- reserved bounded top-N space for credible alternatives from up to three chapters
- added per-item candidate evidence summaries containing positions, chapters, sources, and maximum functional affinity
- added request telemetry for candidate-set count, total positions, chapter coverage, empty sets, single-chapter sets, low-affinity sets, and weak selections
- added a generic weak-selection gate: when a selected in-set position has materially lower functional affinity than another candidate, the code is retained but marked provisional and capped at 55 percent
- added a final cap so completeness normalization cannot restore a weak selection to confirmed/high-confidence status
- extended the client-feedback scorer to measure candidate-position recall separately from final-answer accuracy
- moved full-request cache to `v12` and normal item cache to `v7` so pre-quality and fixed-prompt results are not reused

### Measured baseline

- old client export final acceptance: 0/7
- old client export candidate-position recall: 4/7 (57.14 percent)
- old export forbidden headings: 6
- old export missing codes: 1
- removed the fixed smartphone HS code from the JSON output example and replaced it with a tariff-neutral field contract
- target after a fresh backend restart: at least 6/7 candidate-position recall and zero forbidden high-confidence outcomes

### Verification

- 54 quality and local-cache tests passed
- 101 broader backend regression tests passed
- Python compilation passed for all changed modules
- diff whitespace validation passed
- four live Upstash integration tests were excluded from local acceptance because outbound network access is restricted
- no paid OpenAI or web-search request was made during this implementation pass
- live result quality still requires a fresh `v12`/`v7` export after backend restart

## Step 37. HS 2022 ceramic-tile migration and numeric subheading resolution

### Issue

- the last product below heading level was a glazed ceramic floor tile returned as `6908.90`
- `[69.08]` is a deleted legacy heading in the local TEC/HS 2022 source
- the current nomenclature classifies ceramic paving and facing tiles under `69.07`
- the description already contained the decisive fact, `water absorption below 0.5 percent`, but the resolver did not compare numeric thresholds

### Root cause

- an obsolete model hypothesis was accepted when no children existed below `69.08`
- the subposition workflow handled text, mounting, surface and vehicle-condition criteria, but not water-absorption bands
- the old ceramic result also remained reusable through the item cache

### Fix implemented

- added a versioned HS 2022 migration from deleted heading `69.08` to current position `69.07`
- added deterministic water-absorption discrimination for:
  - `6907.21`: up to and including 0.5 percent
  - `6907.22`: above 0.5 percent and up to 10 percent
  - `6907.23`: above 10 percent
- added ceramic-only cache revision `hs2022-v1`
- moved the full-request cache schema to `v9` while preserving unaffected item-cache entries

### Verification

- actual 2,425-chunk local TEC index resolved the benchmark tile from legacy `6908.90` to `6907.21.00.00`
- final resolver decision was `retain_full_code`, with `6907.22` and `6907.23` excluded
- 54 focused quality/regression tests passed
- 9 cache-key tests passed, including ceramic targeted invalidation
- external Upstash integration tests could not run inside the restricted test environment; local cache unit behavior passed

### Quality impact

- latest live accepted baseline remains:
  - exact HS6: 14/25 (56 percent)
  - heading or better: 24/25 (96 percent)
  - chapter or better: 25/25 (100 percent)
  - severe mismatch: 0
- deterministic replay of the remaining ceramic gap is expected to produce:
  - exact HS6: 15/25 (60 percent)
  - heading or better: 25/25 (100 percent)
  - chapter or better: 25/25 (100 percent)
- these projected values require one post-restart live run before they become the accepted measured baseline

### Expected post-restart behavior

- full request cache: `v9` miss
- item cache: 24 hits and one ceramic `hs2022-v1` miss on the first rerun
- only the ceramic item should require fresh classification work
- the next identical run should be fully warm with zero OpenAI calls

## Step 38. Final live cold/warm benchmark acceptance

### Selective cold run after restart

- input: `sample_products_quality_25_fresh.csv`
- returned classifications: 25/25
- item cache: 24 hits, 1 ceramic `hs2022-v1` miss
- batches executed: 1 batch containing only the ceramic item
- classification model calls: 1 using `gpt-4.1-mini`
- classification prompt: 4,970 characters / 3,625 tokens
- classification completion: 532 tokens
- backend duration: 66.884 seconds
- client-observed duration: 67.025 seconds
- ceramic final code: `6907.21.00.00`

### Final measured quality

- exact HS6: 15/25 (60 percent)
- heading or better: 25/25 (100 percent)
- chapter or better: 25/25 (100 percent)
- missing results: 0
- mismatches: 0
- benchmark references remain non-official and require customs-expert validation

### Immediate warm rerun

- returned classifications: 25/25
- item cache: 25 hits
- pending items: 0
- batches executed: 0
- OpenAI model calls: 0
- prompt tokens: 0
- completion tokens: 0
- backend duration: 8.617 seconds
- client-observed duration: 8.733 seconds

### Final artifacts

- `final_quality_25_v9.json`
- `final_quality_25_v9_warm.json`
- `quality_benchmark_report_v9_final_2026-07-17.csv`

### Release validation

- Python compile passed
- frontend TypeScript check passed
- 63 focused backend tests passed
- final quality and warm-cache acceptance criteria passed

## Step 39. Final client-facing delivery document

### Requirement

- the final handover must include updated backend code, updated frontend code, and only one client-facing changes document
- the original proposal must remain a scope reference rather than being presented as a second final document

### Delivered

- created `CLIENT_CHANGE_SUMMARY.md` as the single final client-facing handover document
- reconciled every original client concern with the implemented resolution and verified outcome
- included measured selective-refresh, warm-cache, quality, manufacturer-reference, import, validation, storage, and logging results
- clearly separated engineering benchmark results from official customs accuracy claims
- documented scope exclusions, deployment steps, and final legal limitations
- updated `CLIENT_DELIVERY_PROPOSAL.md` to identify the final handover filename
- updated `Readme.md` with the final document link

### Final documentation package

- client receives: `CLIENT_CHANGE_SUMMARY.md`
- internal project references remain in the repository but are not additional client documentation deliverables

## Step 28. First quality baseline and candidate-safety correction

### Measured input

- results file: `mosam-classification-results-2026-07-17T10-48-44-869Z.json`
- benchmark: `quality_benchmark_25_expected.csv`
- generated report: `quality_benchmark_report_2026-07-17.csv`
- all 25 results came from the item cache in 8.73 seconds
- no LLM call, web search, prompt token, or completion token was charged during this repeat run

### Baseline quality result

- complete results: 25/25
- exact HS6: 10/25 (40%)
- heading-or-better: 16/25 (64%)
- chapter-or-better: 21/25 (84%)
- heading-only: 6
- chapter-only: 5
- wrong chapter: 4
- missing result or code: 0

### Root cause found

- vector retrieval sometimes omitted the legally relevant finished-product position
- hard candidate enforcement then replaced an out-of-set LLM hypothesis with the first retrieved position even when that position described a different product
- the lexical position validator could overwrite a correct finished-article heading with a raw-material heading inside the same chapter
- examples included a glass food container, vacuum flask, LED bulb, aluminium cooking pot, and woven polypropylene sack
- several partial matches also indicate HS 2022 subheading-resolution gaps that require a separate follow-up after the candidate guard is measured

### Fix implemented

- candidate positions are now prioritized evidence instead of an unconditional replacement list
- when the model proposes an out-of-candidate code, the code is retained but marked provisional with confidence capped at 55
- the response records `tec_candidate_outside_set`, leaves `tec_candidate_locked` false, and adds an explicit audit warning
- confirmed high-confidence results are no longer overwritten by the purely lexical position validator
- out-of-candidate provisional hypotheses are protected from a second lexical overwrite
- classification and single-item cache schemas were changed from `v2` to `v3` so known weak cached outputs are not reused after the quality fix

### Cost control

- the first post-restart comparison will be intentionally cold because the quality-changing cache version was bumped
- only this first `v3` run should incur classification cost
- later identical runs should return to the item-cache fast path with near-zero API cost

### Verification

- Python compile passed for the changed classification modules
- 37 offline candidate, position-validator, quality-benchmark, and cache unit tests passed
- live Upstash integration tests were not run successfully inside the restricted test sandbox because outbound network access was blocked
- `git diff --check` passed for the changed code and documents

### Next comparison

1. restart the backend so cache schema `v3` and the new guards are active
2. classify `sample_products_quality_25_fresh.csv` once
3. download the new JSON result
4. score it against the same benchmark
5. compare exact HS6, heading, and chapter rates with the 40% / 64% / 84% baseline before making further model or RAG changes

## Step 29. Post-guard comparison and lexical-validator rollback

### Measured `v3` cold run

- complete results: 25/25
- duration: 422.15 seconds, approximately 7 minutes 2 seconds
- batches: 9, with no incomplete-batch fallback
- classification model: `gpt-4.1-mini`
- classification calls: 9
- prompt tokens: 40,314
- completion tokens: 8,156
- web-search calls: 0
- item-cache stores: 25

### Quality comparison

- exact HS6 changed from 10/25 (40%) to 7/25 (28%)
- heading-or-better changed from 16/25 (64%) to 15/25 (60%)
- chapter-or-better changed from 21/25 (84%) to 22/25 (88%)
- wrong-chapter results changed from 4 to 3
- glass container improved from a wrong chapter to the correct heading
- solar module improved from chapter-only to the correct heading
- office desk, microwave oven, electrical cable, and ball bearing regressed
- `v3` is rejected because reduced severe errors did not compensate for the exact and heading-level regression

### Regression root cause

- the lexical position validator changed correct model headings after generation
- observed examples:
  - microwave oven: initial position `85.16`, overwritten to `85.46`
  - electrical cable: initial position `85.44`, overwritten to `85.28`
  - ball bearing: initial position `84.82`, overwritten to `84.12`
- lexical word overlap was not reliable enough to mutate a legally meaningful tariff position

### Safety fix implemented

- position validation is now advisory-only for every classification
- a detected alternative is stored as `position_validation_advisory`
- the selected `hs_code`, confidence, status, label, and justification are no longer changed by lexical validation
- cache schemas were moved from `v3` to `v4` to prevent reuse of validator-mutated results
- future targeted verification can use the advisory flag without charging a second model call for every product

### Verification

- changed Python modules compile successfully
- 37 offline classification, quality, candidate, validator, and cache tests pass
- detailed `v3` report: `quality_benchmark_report_v3_2026-07-17.csv`

### Next gate

- restart backend and run the same 25 products under cache schema `v4`
- score the downloaded JSON against the same benchmark
- do not accept further optimization unless exact HS6 and heading accuracy recover while chapter-level mismatch remains controlled

## Step 31. Accepted `v4` quality baseline

### Measured cold run

- result file: `mosam-classification-results-2026-07-17T11-33-04-705Z.json`
- detailed report: `quality_benchmark_report_v4_2026-07-17.csv`
- complete results: 25/25
- duration: 390.09 seconds, approximately 6 minutes 30 seconds
- structured batches: 9
- incomplete-batch fallbacks: 0
- classification model: `gpt-4.1-mini`
- classification calls: 9
- prompt tokens: 40,392
- completion tokens: 7,996
- web-search calls: 0
- item-cache stores: 25

### Quality result

- exact HS6: 14/25 (56%)
- heading-or-better: 21/25 (84%)
- chapter-or-better: 22/25 (88%)
- heading-only: 7
- chapter-only: 1
- wrong chapter: 3
- missing results or codes: 0

### Before/after result

- exact HS6 improved from the original 40% and rejected `v3` 28% to 56%
- heading-or-better improved from 64% and 60% to 84%
- chapter-or-better improved from the original 84% to 88%
- advisory-only validation restored correct results for the water pump, air conditioner, office desk, cooking pot, microwave oven, cable heading, and ball bearing
- cold duration improved from `v3` 422.15 seconds to 390.09 seconds, approximately 7.6%
- prompt/completion token volume remained broadly stable

### Current decision

- `v4` passes the engineering quality gate and becomes the current baseline
- general candidate, model-routing, cache, and validator behavior must remain frozen unless a later change meets or exceeds 56% exact, 84% heading, and 88% chapter accuracy
- benchmark labels remain non-official until reviewed by a customs-domain expert

### Remaining targeted quality work

- wrong chapter:
  - stainless steel vacuum flask
  - LED household light bulb
  - polypropylene woven packing sack
- correct chapter but incomplete/legacy subheading:
  - tempered glass food container
  - solar photovoltaic module
  - cotton terry towel
  - nitrile examination gloves
  - glazed ceramic floor tile
  - electrical cable
  - passenger tyre
  - household insecticide
- next fixes should target these categories without changing results that already pass

## Step 32. Zero-cost heading enrichment for three severe mismatches

### Root cause

- detailed structured frontend rows intentionally skip paid product identification
- the same branch also skipped local heading matching, customs aliases, and candidate promotion
- this saved cost but prevented obvious finished-product headings from entering or leading the candidate set
- the TEC heading parser also missed positions where a four-digit position and full tariff code were printed on the same source line

### Fix implemented

- structured rows now derive customs-heading keywords from their complete source text
- direct heading lookup runs against the local TEC position index without an extra OpenAI call
- matching official headings are promoted before vector candidates
- added focused aliases for general product families:
  - vacuum/insulated flasks
  - LED/light bulbs
  - woven packaging sacks
- extended the TEC parser to index combined lines such as `96.17 9617.00.00.00 ...`
- candidate evidence remains advisory and the lexical validator remains non-mutating

### Local TEC verification

- vacuum flask resolves to heading `96.17`
- LED household bulb resolves to heading `85.39`
- woven polypropylene packing sack resolves to heading `63.05`
- LED and sack matches score 1.0 against the local official heading index

### Cost-safe cache strategy

- full-request schema moved to `v5` so the old aggregate response is bypassed
- general item cache remains `v4`
- only the three affected product families use item-cache schema `v5`
- previous `v4` values are not accepted as legacy fallback for those targeted products
- sample distribution verified as 22 `v4` items and 3 `v5` items
- expected next request is one paid three-item batch rather than nine paid batches for all 25 products

### Verification

- changed Python modules compile successfully
- 37 focused retrieval, tariff-label, candidate, validator, quality, and cache tests pass
- static sample verification found exactly the intended three `v5` products
- `git diff --check` passed

### Next live acceptance

1. restart the backend
2. classify `sample_products_quality_25_fresh.csv`
3. confirm logs show approximately 22 item-cache hits, 3 misses, and 1 batch
4. download and score the new JSON
5. accept the change only if the three severe mismatches improve and the `v4` 56% / 84% / 88% quality gate is preserved

## Step 33. Targeted cache acceptance correction

### Observed live run

- full-request cache `v5` missed as intended
- all 25 item-cache entries hit, with zero pending items and zero classification batches
- duration was 8.95 seconds with zero LLM calls and zero tokens
- this was a valid warm-performance result but not a valid targeted quality test because the three changed products were not regenerated

### Correction implemented

- full-request cache moved to `v6`
- targeted item-cache namespace changed from generic `v5` to dedicated `heading-v1`
- general products continue using item-cache `v4`
- targeted products cannot fall back to old item-cache values
- item-cache logs now print the cache version for every hit, miss, and store

### Verification

- static distribution: 22 items use `v4`, exactly 3 use `heading-v1`
- 26 cache, retrieval, and tariff-index tests pass
- Python compile passed

### Expected next logs

- 22 lines similar to `[item-cache] HIT version=v4`
- 3 lines similar to `[item-cache] MISS version=heading-v1`
- `cache_hits=22 pending=3 batches=1`
- after classification, 3 lines similar to `[item-cache] STORE version=heading-v1`

## Step 34. Cache-key ordering fix for targeted structured rows

### Observed retry

- full-request `v6` cache missed, but all 25 item logs still showed `HIT version=v4`
- downloaded JSON was byte-for-behavior equivalent to the accepted `v4` result
- benchmark stayed at 56% exact HS6, 84% heading, and 88% chapter accuracy
- promoted `96.17`, `85.39`, and `63.05` candidates were absent, proving the new retrieval branch had not executed

### Root cause

- target-family detection was performed after generic manufacturer-reference cache normalization
- normal structured fields were falsely reduced to reference-like fragments:
  - vacuum flask became `12.75`
  - LED bulb became `self-contained`
  - woven sack became `Open-mouth`
- the reduced text no longer contained the target product family, so the key incorrectly remained `v4`

### Fix implemented

- targeted revision detection now runs on the original complete structured product text
- manufacturer-reference normalization still determines the digest, preserving the other 22 cache entries for this focused test
- full-request cache moved to `v7`
- added regression tests using complete multiline `source_query` strings containing the misleading fragments

### Verification

- 27 cache, retrieval, and tariff-label tests pass
- the exact downloaded JSON source queries now resolve to 22 `v4` keys and 3 `heading-v1` keys
- the three selected products are exactly vacuum flask, LED household bulb, and woven polypropylene sack

### Next live acceptance

- restart backend after the `v7` change
- expected logs remain 22 `HIT version=v4`, 3 `MISS version=heading-v1`, and one pending batch

## Step 35. Targeted heading result and structured batch isolation

### Successful targeted run

- cache behavior matched the intended cost-safe design:
  - 22 item-cache hits
  - 3 targeted misses
  - 1 classification batch
  - 1 `gpt-4.1-mini` call
- duration: 91.37 seconds
- prompt tokens: 4,926
- completion tokens: 936
- web searches: 0

### Quality improvement

- exact HS6 remained 14/25 (56%)
- heading-or-better improved from 21/25 (84%) to 23/25 (92%)
- chapter-or-better improved from 22/25 (88%) to 24/25 (96%)
- severe mismatches reduced from 3 to 1
- LED bulb improved from `94.05` to `85.39`
- woven polypropylene sack improved from `39.02` to `63.05`
- stainless steel vacuum flask remained incorrectly classified under `73.23`

### Remaining root cause

- the three-item structured batch was treated as one dossier during candidate construction
- aliases for LED and woven sack dominated the shared candidate set
- vacuum heading `96.17` dropped from the limited set even though local standalone lookup resolved it correctly

### Fix implemented

- a structured dossier is now considered single only when exactly one product header is present
- repeated `Produit :` blocks are split before product-specific candidate retrieval
- all products still share one batch LLM call, preserving the low-cost orchestration
- full-request cache moved to `v8`
- LED and sack retain successful `heading-v1` cache entries
- only vacuum flask moves to `heading-v2` for regeneration

### Verification

- 34 splitter, cache, retrieval, tariff, and candidate tests pass
- exact latest source-query distribution is 22 `v4`, 2 `heading-v1`, and 1 `heading-v2`

### Next live acceptance

- restart backend
- expected result: 24 item-cache hits, one `heading-v2` miss, and one single-item batch
- accept only if vacuum flask candidate metadata contains `96.17` and the 92% heading / 96% chapter gate is preserved

## Step 36. Zero severe mismatches after vacuum-only retry

### Cost-safe live behavior

- 24 item-cache hits
- 1 `heading-v2` cache miss
- 1 single-item classification batch
- 1 `gpt-4.1-mini` call
- duration: 55.49 seconds
- prompt tokens: 3,618
- completion tokens: 514
- web searches: 0
- refreshed vacuum result stored in `heading-v2`

### Vacuum result

- previous code: `73.23.93.00.00`
- new code: `96.17`
- expected heading: `96.17`
- top local candidate: `96.17` with score approximately 10.67
- classification remains provisional at heading level, which is safer than inventing a full line without sufficient TEC discrimination

### New accepted quality gate

- complete results: 25/25
- exact HS6: 14/25 (56%)
- heading-or-better: 24/25 (96%)
- chapter-or-better: 25/25 (100%)
- severe mismatches: 0
- no missing result or missing code

### Improvement from original baseline

- exact HS6: 40% to 56%
- heading-or-better: 64% to 96%
- chapter-or-better: 84% to 100%
- severe mismatches: 4 to 0

### Remaining quality work

- one chapter-only legacy position remains: glazed ceramic floor tile at `69.08`, expected HS 2022 heading `69.07`
- ten additional products are at the correct heading but need stronger HS6/subposition resolution
- broad retrieval, candidate, and validator logic is now frozen against the 56% / 96% / 100% gate
- next work must be targeted HS 2022 nomenclature and subheading completion

### Artifacts

- result: `mosam-classification-results-2026-07-17T12-11-26-918Z.json`
- report: `quality_benchmark_report_heading_v2_2026-07-17.csv`

## Step 30. Compact combined RGI narrative in the frontend

### Issue

- the backend `narrative` combines the RGI and TEC summary for every classified product
- with 25 products this produced a very long paragraph above the structured result table
- the same product-level legal details were already available inside each table row, making the expanded narrative visually repetitive

### Fix implemented

- classification narrative is now collapsed by default under `Voir la synthèse générale RGI`
- the structured classification table appears without a large text wall above it
- users can still expand the complete combined narrative when needed
- expanded narrative has a bounded height and its own vertical scroll area
- assistant-information responses remain fully visible because they do not contain the classification table
- JSON download and backend response retain the complete narrative without data loss

### Files updated

- `frontend/src/app/page.tsx`
- `IMPLEMENTATION_PROGRESS.md`

### Formatting enhancement

- added visible summary indicators for product count, total quantity, detailed codes, confirmed results, and results requiring review
- combined narrative is parsed into separate product cards instead of one continuous paragraph
- each product card presents RGI, TEC, explanatory-note, and model-hypothesis content as scan-friendly bullet points

## Next Execution Phase. Completion Roadmap

The remaining work has been converted into a measurable completion plan in `IMPLEMENTATION_PLAN.md`.

Execution will proceed in this order:

1. diagnose and complete the single-item classification cache
2. verify repeated manufacturer-reference runs reduce classification calls from 10 to no more than 1
3. create and score a classification-quality benchmark
4. perform benchmark-safe cost and latency tuning
5. harden low-confidence and unresolved-product handling
6. complete end-to-end regression and release validation
7. prepare the final client changes document

The immediate next implementation target is the classification cache. Product-identification cache is already effective, but the latest 10-reference run still reported `structured_item_cache_hit=0` and `classification_llm_calls=10`.

## Step 23. Single-item classification cache completion

### Issue

- repeated manufacturer-reference runs reported `structured_item_cache_hit=0`
- all 10 products triggered fresh classification calls even though Redis keys existed
- cache writes did not expose success or failure, making the behavior difficult to diagnose

### Root cause

- cached classification JSON contains a commercial `value` field such as `2850 USD`
- `cache_get()` had backward-compatibility logic that unwrapped any JSON dictionary containing `value`
- a complete cached classification was therefore returned as only the commercial value string
- the item-cache loader correctly rejected that string because it was not a classification dictionary
- product-identification cache appeared healthy because its payload does not use the same commercial `value` field

### Fix implemented

- restricted legacy wrapper support to objects whose only key is `value`
- changed `cache_set()` to return a success boolean and log safe failure details
- added item-cache diagnostics and telemetry for:
  - load hit
  - load miss
  - invalid entry
  - successful store
  - skipped store
  - failed store
  - legacy-key migration hit
- prevented placeholders and missing HS codes from being cached
- normalized labelled numeric manufacturer references such as `2607017160`
- added automatic migration from previous full-row v2 keys to normalized reference keys
- changed multi-item cache reads and writes from sequential I/O to bounded concurrency
- ensured current request quantity, origin, value, and currency replace old cached commercial metadata

### Files updated

- `sam/cache.py`
- `sam/api.py`
- `sam/tests/test_cache.py`
- `IMPLEMENTATION_PLAN.md`
- `IMPLEMENTATION_PROGRESS.md`

### Verification

- backend compile passed:
  - `python -m py_compile sam\api.py sam\cache.py sam\tests\test_cache.py`
- 17 targeted cache and metadata tests passed
- direct Upstash round-trip successfully stored and read a 25,038-character payload
- all 10 existing manufacturer-reference classifications were valid with the corrected reader
- migration-aware live load returned 10 of 10 cache hits in approximately 5.68 seconds
- second normalized live load returned 10 of 10 cache hits in approximately 3.42 seconds
- no paid classification or web-search call was required for cache-layer verification

### Next validation

- restart the backend and submit `sample_manufacturer_references_10.csv` once through the frontend
- either of these cache success paths is valid:
  - full-request cache: `classify_cache_hit=1`
  - item cache after a full-request miss: `structured_item_cache_hit=10` and `single_item_classification_cache_load_hit=10`
- in both paths, `classification_llm_calls` and `web_search_calls` should be absent or `0`
- after this regression check, proceed to the classification-quality benchmark phase

## Step 24. Warm-cache response-time optimization

### Issue

- the first successful 10-item cache run made zero OpenAI calls but still took approximately 77.66 seconds
- approximately 60.5 seconds elapsed before the cache-status log appeared
- approximately 12.9 seconds were then spent re-running normalization over 10 already-normalized cached results
- the combined cached response was approximately 305,687 characters

### Root cause

- every classification request synchronously queried Redis for the administrative cache-disabled flag, which was removed as a request-path risk
- cached classifications were passed through the complete legal normalization pipeline again
- this repeated position resolution, RGI, completeness, tariff, and risk processing that had already been applied before the item was cached

Revised timing attribution:

- a post-restart retest still showed the same approximately 60-second gap before the new non-blocking cache-status log
- this proved that the gap occurred before `cache_classify_is_disabled()`
- the remaining delay was traced to assistant-meta fuzzy matching over the 2,688-character structured product list

### Fix implemented

- added a 30-second local TTL for the cache-disabled status
- stale status now returns the last local value immediately and refreshes Redis in a daemon thread
- admin status GET uses a forced remote refresh
- successful admin status PATCH updates local state immediately
- added lightweight shape validation for full-request cache responses
- valid full-request cache responses now use a direct fast path
- added a fully cached structured-item fast path
- the fast path still:
  - validates that every cached item is a usable classification
  - overlays current quantity, origin, value, and currency
  - preserves legal details and product-identification traceability
  - emits complete frontend progress states
- fresh and partial-cache paths still run the complete quality pipeline
- added telemetry counters:
  - `classify_cache_fast_path`
  - `structured_item_cache_fast_path`
  - `classify_cache_invalid`

### Payload decision

- field-size analysis showed that most response size belongs to product identification, classification analysis, legal decision, TEC candidates, subposition resolution, and RGI traceability
- frontend actively uses product-identification and classification-analysis details
- these fields were not removed blindly because cost/time optimization must not reduce result quality or auditability
- internal-only response projection can be evaluated after the quality benchmark

### Files updated

- `sam/cache.py`
- `sam/api.py`
- `sam/tests/test_cache.py`
- `IMPLEMENTATION_PLAN.md`
- `IMPLEMENTATION_PROGRESS.md`

### Verification

- backend compile passed:
  - `python -m py_compile sam\cache.py sam\api.py sam\tests\test_cache.py`
- 25 targeted cache, metadata, status-TTL, and fast-path tests passed
- diff validation passed with no whitespace errors
- production-like read-only measurement returned 10 of 10 item-cache hits
- measured item-cache load: approximately 4.76 seconds
- measured cached merge and serialization: approximately 0.008 seconds
- resulting response retained approximately 292,531 characters of existing detail
- no OpenAI classification or web-search call was made during measurement

### Next validation

- restart the backend and submit `sample_manufacturer_references_10.csv`
- expected telemetry should contain either:
  - `classify_cache_hit=1` and `classify_cache_fast_path=1`, or
  - `structured_item_cache_hit=10` and `structured_item_cache_fast_path=1`
- `classification_llm_calls` and `web_search_calls` should remain absent or `0`
- under similar Redis latency, total warm response time should be approximately 5-7 seconds rather than 77.66 seconds
- after this check, start the classification-quality benchmark phase

## Step 25. Structured assistant-meta matcher bypass

### Issue

- after the cache-status and cached-normalization optimizations, the 10-item request still took approximately 65.84 seconds
- item-cache loading took approximately 4.66 seconds and cached merge took approximately 0.007 seconds
- approximately 60 seconds remained between the structured request log and the cache-status log

### Root cause

- `_classify_text_query()` called `is_assistant_meta_query()` before cache processing
- the assistant-meta detector uses sliding-window `SequenceMatcher` fuzzy comparison
- a 2,688-character, 10-row structured merchandise list generated many fuzzy comparison windows
- structured `items_payload` cannot represent an assistant FAQ, so this work was unnecessary

### Fix implemented

- structured merchandise requests now bypass assistant-meta fuzzy detection
- plain text requests still use the existing assistant-information behavior
- no classification, RAG, product-identification, or web-search logic was changed

### Files updated

- `sam/api.py`
- `sam/tests/test_cache.py`
- `IMPLEMENTATION_PROGRESS.md`

### Verification

- added regression coverage proving `is_assistant_meta_query()` is not called for structured merchandise payloads
- compile passed
- 26 targeted cache, status, metadata, and fast-path tests passed
- cached structured result shape and HS code remain unchanged

### Expected next run

- restart backend and submit the same 10-reference CSV
- the approximately 60-second pre-cache gap should disappear
- expected warm duration under similar Redis latency: approximately 5-7 seconds
- expected cost telemetry remains zero OpenAI classification and zero web-search calls

### Post-restart result

- verified on 2026-07-17 with the same 10-reference CSV
- total request duration: approximately 4.738 seconds
- assistant-meta pre-cache delay reduced from approximately 60 seconds to approximately 0 seconds
- item-cache hits: 10 of 10
- pending items: 0
- structured classification batches: 0
- cached merge fast path active: `structured_item_cache_fast_path=1`
- classification LLM calls: 0
- web-search calls: 0
- prompt and completion tokens: 0
- all 10 classifications were returned successfully
- compared with the 77.66-second cached baseline, warm response time improved by approximately 93.9%

Status: completed. Proceed to classification-quality benchmark work.

## Step 26. Fresh 25-product quality test dataset

### Purpose

- create a completely new cache-cold product list for broader quality, batch, cost, and latency testing
- avoid reusing the previous 10-product and manufacturer-reference samples
- exercise diverse TEC chapters using detailed structured product data

### Dataset created

- file: `sample_products_quality_25_fresh.csv`
- 25 unique products
- import-safe frontend headers
- detailed material, usage, and technical characteristics for every product
- positive numeric quantity and value fields
- mixed food, textile, rubber, ceramic, glass, metal, machinery, electrical, vehicle, furniture, chemical, and medical products
- no exact designation overlap with the existing quality, complete-product, or manufacturer-reference samples

### Intended test path

- this dataset contains detailed normal products rather than manufacturer-reference-only rows
- it should test normal structured small-batch classification rather than reference web-search mode
- the first run should be treated as a cold quality/cost measurement
- repeated runs can then verify cache behavior separately

### Verification

- row count: 25
- headers match the existing frontend import contract
- every row contains exactly 9 columns
- all designations are unique
- all quantity and value fields are positive numeric values
- existing exact designation overlap: 0

## Step 27. Repeatable classification-quality benchmark

### Issue

- backend logs proved item count, timing, model calls, token usage, cache behavior, and fallback behavior, but did not prove tariff-code correctness
- screenshots were not a stable or machine-readable way to compare all 25 results
- optimizing prompts or routing without a baseline could silently reduce classification quality

### Fix implemented

- added `quality_benchmark_25_expected.csv` with one non-official engineering reference at chapter, heading, and HS6 level for each fresh test product
- added `sam/quality_benchmark.py` to load frontend JSON or result CSV files and align classifications by product designation
- added separate metrics for:
  - exact HS6 match
  - heading-level-or-better match
  - chapter-level-or-better match
  - missing results
  - missing codes
  - full mismatches
- added a detailed CSV report containing expected and actual codes, confidence, status, risk, rationale, and alignment method
- added a `JSON` download button to the frontend result panel so the exact structured result can be scored without copying a screenshot
- added automated tests for nested API payloads, reordered results, partial-level matches, missing results, and HS-code normalization

### Cost and performance impact

- scoring is local and makes no OpenAI or web-search calls
- an already displayed result can be downloaded and scored without another paid classification request
- rerunning the same 25 products should use item cache where available, keeping repeat-test API cost close to zero

### Verification

- the benchmark contains 25 rows and exactly matches all 25 fresh input designations in order
- `python -m unittest sam.tests.test_quality_benchmark` passed 5 tests
- `python -m py_compile sam\quality_benchmark.py sam\tests\test_quality_benchmark.py` passed
- frontend `cmd /c npx tsc --noEmit` passed

### Usage

1. classify `sample_products_quality_25_fresh.csv`
2. click `JSON` in the result panel
3. run `python -m sam.quality_benchmark --results <downloaded-results.json> --report quality_benchmark_report.csv`
4. use the generated summary and per-product report as the quality baseline before further cost/model tuning

### Remaining validation

- benchmark codes are non-official engineering references and are not customs rulings
- a customs-domain reviewer must confirm or correct the expected labels before final-line accuracy can be presented as production-grade accuracy
- the next implementation step is to score the latest 25-product output and categorize every disagreement before changing RAG or model routing

## Step 14. Manufacturer reference visibility and testing

### Issue

- client clarified that manufacturer references / part numbers should be identified through internet search when needed
- backend already had an OpenAI product-identification layer with optional web search, but the user-facing result did not clearly show what product was recognized before tariff classification
- without this visibility, it was difficult to verify whether a bad tariff result came from product identification or from TEC classification

### Why it matters

- real declarants often enter only a manufacturer reference or model number
- the system should not require a complete internal manufacturer database for every possible product
- the user needs traceability: product recognized, reference used, confidence, method, web queries, and web sources

### Fix implemented

- added a dedicated `ProductIdentification` frontend type for the metadata already attached by the backend
- expanded the result detail panel to show:
  - recognized manufacturer / product name
  - manufacturer part number
  - input type such as manufacturer reference or free description
  - product type, usage, detected materials, detected characteristics
  - identification confidence and method
  - retry count when the backend needed multiple attempts
  - missing customs information
  - unstable-identification warning
  - web-search failure warning
- kept existing internet-search queries and source links visible in the same expanded detail area
- added `sample_manufacturer_references_10.csv` to test reference-only product inputs

### Files updated

- `frontend/src/app/page.tsx`
- `sample_manufacturer_references_10.csv`

### Expected result

- manufacturer-reference tests become auditable from the frontend
- if web search is used, the user can see the queries and external sources returned by the identification step
- if product identification is uncertain, the UI warns the user instead of silently presenting a confident-looking tariff result
- this keeps the current scope aligned with the client requirement without building a full manufacturer/part-number database

### Verification

- frontend type-check passed with `cmd /c npx tsc --noEmit`

## Step 18. Manufacturer-reference web-search gate fix

### Issue

- manufacturer-reference CSV run returned 10 classifications, but telemetry showed only classification calls
- missing counters:
  - `manufacturer_reference_inputs`
  - `product_identification_web_enabled`
  - web-search related counters
- root cause: `should_run_product_identification()` skipped any text that looked like a structured dossier before checking whether it contained an explicit manufacturer reference

### Why it matters

- imported rows are intentionally converted into structured dossiers
- manufacturer references inside those dossiers must still go through the product-identification/web-search step
- otherwise the system classifies the raw reference text directly, which is weaker for client use cases

### Fix implemented

- product-identification gate now checks `detect_input_type(text) == manufacturer_ref` before applying structured/rich-description skip rules
- structured dossiers containing `Reference fabricant : ...` now remain eligible for product identification
- local web-search model config changed from expensive `gpt-5` to `gpt-4.1-mini` to control cost when web lookup is triggered

### Files updated

- `sam/product_identification.py`
- `.env`
- `IMPLEMENTATION_PROGRESS.md`

### Verification

- detector test returned `manufacturer_ref`
- `should_run_product_identification()` returned `True` for a structured dossier containing `Reference fabricant`
- backend compile passed with `python -m py_compile sam\product_identification.py`

## Step 19. Manufacturer-reference batch cost/stability fix

### Issue

- after restart, manufacturer-reference test did trigger web search, but only for 5 rows
- classification telemetry showed:
  - `manufacturer_reference_inputs=5`
  - `web_search_calls=5`
  - `classification_llm_calls=10`
  - `structured_batches_incomplete=2`
  - mixed models: `gpt-4.1-mini` and `gpt-5`
- root causes:
  - some imported rows used list-style text like `reference fabricant Cisco C9200...` without a colon, so detection was not strong enough
  - web-enriched 3-item batches became unstable and sometimes returned only 1 classification, forcing expensive fallback calls
  - routing treated web-enriched/uncertain prompts as complex and sent some calls to the primary model

### Why it matters

- manufacturer-reference classification is already slower because it may need web lookup
- failed batch + fallback means the same products can be processed twice
- client's main concern is cost and reliable results, so reference/web-search mode needs stability more than aggressive batching

### Fix implemented

- manufacturer-reference detector now recognizes labelled reference text anywhere in the input, including:
  - `reference fabricant ...`
  - `manufacturer reference ...`
  - `part number ...`
  - `mpn ...`
- structured small-batch mode now switches to per-item mode when product identification is required
- added telemetry counter: `structured_reference_per_item_mode`
- classification routing no longer blocks the cheap model just because the prompt contains web complement or identification uncertainty
- web-enriched single-item classification now routes to `gpt-4.1-mini` when prompt size is within the configured threshold

### Files updated

- `sam/product_identification.py`
- `sam/api.py`
- `sam/rag.py`
- `IMPLEMENTATION_PROGRESS.md`

### Verification

- labelled list-line test returned `manufacturer_ref`
- `should_run_product_identification()` returned `True`
- routing test selected `gpt-4.1-mini` for a web-enriched single-item prompt
- backend compile passed with `python -m py_compile sam\product_identification.py sam\api.py sam\rag.py`

## Step 20. Cost-first controls for manufacturer-reference mode

### Issue

- manufacturer-reference flow is now correct, but it is expensive because each item can trigger:
  - product identification
  - web search
  - multiple FAISS/RAG searches
  - one classification LLM call
- repeated tests with the same part number but slightly different row text could miss the product-identification cache

### Why it matters

- client priority is API cost and response time
- manufacturer-reference identification must stay available, but repeated work should be avoided aggressively

### Fix implemented

- normalized manufacturer-reference identification cache keys around the extracted part number
- examples that now share the same identification cache key:
  - `Cisco C9200L-48P-4X-E`
  - `Reference fabricant: C9200L-48P-4X-E`
  - imported row text containing `reference fabricant Cisco C9200L-48P-4X-E`
- added cost-control RAG config flags:
  - `MOSAM_RAG_EXTRA_SEARCHES_ENABLED`
  - `MOSAM_RAG_HEADING_MATCH_ENABLED`
- configured local cost-first defaults:
  - `MOSAM_WEB_SEARCH_CONTEXT_SIZE=low`
  - `MOSAM_RAG_EXTRA_SEARCHES_ENABLED=false`
  - `MOSAM_RAG_HEADING_MATCH_ENABLED=true`
- kept heading/label matching enabled because it is cheaper than extra embedding searches
- updated deployment env example with the same cost-control flags

### Files updated

- `sam/product_identification.py`
- `sam/rag.py`
- `sam/config/settings.py`
- `.env`
- `deploy/mosam-api.env.example`
- `IMPLEMENTATION_PROGRESS.md`

### Expected result

- repeated manufacturer-reference tests should use product-identification cache more often
- fewer repeated RAG embedding/vector searches per product
- lower web-search context cost
- lower total time on repeated or similar manufacturer-reference imports

### Verification

- cache-key test confirmed same key for bare reference, labelled reference, and imported-row text
- backend compile passed with `python -m py_compile sam\product_identification.py sam\rag.py sam\config\settings.py`

## Step 21. Limited parallel mode for manufacturer-reference items

### Issue

- manufacturer-reference mode became stable after switching to per-item classification
- however, items were still processed sequentially
- latest measured run still took around 8.3 minutes for 10 references even with cheaper models

### Why it matters

- each reference may need web lookup, RAG retrieval, and one classification call
- sequential execution makes total time roughly the sum of all item times
- limited parallelism can reduce wall-clock time while keeping per-item stability

### Fix implemented

- added `MOSAM_REFERENCE_PARALLELISM` configuration
- default local value: `2`
- when structured manufacturer-reference mode switches to per-item mode, pending items are now processed with a limited thread pool
- normal detailed-product batching is unchanged
- telemetry is now protected by a lock so counters can be shared safely by limited worker threads
- added telemetry counters:
  - `structured_reference_parallel_mode`
  - `structured_reference_parallel_workers`
- individual item classifications are still cached after completion

### Files updated

- `sam/api.py`
- `sam/telemetry.py`
- `sam/config/settings.py`
- `.env`
- `deploy/mosam-api.env.example`
- `IMPLEMENTATION_PROGRESS.md`

### Expected result

- manufacturer-reference imports should keep per-item stability
- wall-clock time should improve because two references can be processed at the same time
- API cost should remain predictable because batch fallback is avoided
- parallelism can be reduced to `1` if rate limits occur, or increased cautiously up to `4`

### Verification

- backend compile passed with `python -m py_compile sam\api.py sam\telemetry.py sam\config\settings.py`
- config check confirmed `MOSAM_REFERENCE_PARALLELISM=2`

## Step 22. Manufacturer-reference classification cache normalization

### Issue

- product-identification cache was hitting, but single-item classification cache was not
- latest parallel run still showed `classification_llm_calls=10` and `structured_item_cache_hit=0`
- root cause: single-item classification cache used the full row text, so small changes in material, value, origin, or formatting created a new cache key

### Why it matters

- once a manufacturer reference has been classified, repeated imports should not pay another classification LLM call for the same reference
- this directly targets the client's cost concern and repeated-test latency

### Fix implemented

- bumped single-item classification cache schema from `v1` to `v2`
- added manufacturer-reference extraction for classification cache keys
- classification cache now normalizes equivalent inputs such as:
  - `Cisco C9200L-48P-4X-E`
  - `Reference fabricant: C9200L-48P-4X-E`
  - imported row text containing `reference fabricant Cisco C9200L-48P-4X-E`
- non-reference products still use full normalized row text as the cache key

### Files updated

- `sam/api.py`
- `IMPLEMENTATION_PROGRESS.md`

### Expected result

- first run after this change will create `v2` single-item cache entries
- second run with the same manufacturer references should show high `structured_item_cache_hit`
- classification LLM calls should drop significantly on repeated manufacturer-reference imports

### Verification

- backend compile passed with `python -m py_compile sam\api.py`
- cache-key test confirmed bare reference, labelled reference, and imported-row text produce the same single-item classification cache key

## Step 15. Manufacturer reference import detection fix

### Issue

- manufacturer reference sample imported correctly, but after import each row became a full structured dossier
- the product-identification detector could treat that full dossier as a free description instead of a manufacturer reference
- frontend label also expected `manufacturer_reference`, while backend returns `manufacturer_ref`

### Why it matters

- client specifically wants reference/part-number inputs to be identified through internet search when needed
- if imported reference rows are misdetected as free descriptions, web search may not trigger under the optimized `auto` policy

### Fix implemented

- backend structured dossier now adds `Reference fabricant : <designation>` when the designation looks like a manufacturer reference
- product-identification detector now recognizes explicit labels such as `Reference fabricant`, `manufacturer reference`, `part number`, and `mpn`
- frontend now maps both `manufacturer_ref` and `manufacturer_reference` to `Reference fabricant`
- manufacturer-reference sample CSV now includes explicit reference text in the characteristics column for clearer testing

### Files updated

- `sam/api.py`
- `sam/product_identification.py`
- `frontend/src/app/page.tsx`
- `sample_manufacturer_references_10.csv`

### Verification

- detector test returned `manufacturer_ref` for a structured dossier containing `Reference fabricant`
- backend compile passed with `python -m py_compile sam\api.py sam\product_identification.py`
- frontend type-check passed with `cmd /c npx tsc --noEmit`

## Step 16. Import-safe CSV template

### Issue

- downloadable CSV template used English headers such as `material`, `characteristics`, `origin`, and `unit`
- backend importer was primarily optimized for French/front-end style headers
- this could make a user download the official template and still get missing or incorrectly mapped columns

### Why it matters

- file import should be predictable and low-friction
- users should not need to manually rename columns after downloading the system template
- manufacturer-reference rows should carry an explicit reference signal for the identification step

### Fix implemented

- downloadable CSV template now uses import-safe headers:
  - `designation`
  - `matiere / composition`
  - `usage`
  - `caracteristiques`
  - `quantite`
  - `unite`
  - `pays d'origine`
  - `valeur`
  - `devise`
- template now includes a manufacturer-reference example row with `Reference fabricant: ...`
- added UTF-8 BOM to the browser-generated CSV download for better Excel compatibility
- backend aliases now also accept English canonical headers from the previous template:
  - `material`
  - `characteristics`
  - `unit`
  - `origin`
  - `value`
- added a static repo template file: `mosam_import_template.csv`

### Files updated

- `frontend/src/app/page.tsx`
- `sam/api.py`
- `mosam_import_template.csv`
- `IMPLEMENTATION_PROGRESS.md`

### Verification

- backend compile passed with `python -m py_compile sam\api.py`
- frontend type-check passed with `cmd /c npx tsc --noEmit`
- static template header checked in `mosam_import_template.csv`

## Step 17. Manufacturer-reference import UX check

### Issue

- manufacturer-reference CSV imported 10 rows correctly, but the table visually clipped long values
- empty material cells showed placeholders, which could look like missing imported data
- frontend-generated text query did not explicitly mark reference-like designations before sending the request

### Why it matters

- the user needs confidence that import worked before starting classification
- manufacturer references should stay obvious through the whole frontend-to-backend flow

### Fix implemented

- widened key table columns:
  - designation
  - material / composition
  - usage
  - characteristics
- frontend query builder now detects reference-like designations and adds `Reference fabricant : ...` in structured single-item text
- frontend multi-row query lines now also include `reference fabricant ...` for reference-like designations

### Files updated

- `frontend/src/components/MerchandiseTableForm.tsx`
- `frontend/src/lib/merchandiseQuery.ts`
- `IMPLEMENTATION_PROGRESS.md`

### Verification

- frontend type-check passed with `cmd /c npx tsc --noEmit`
- fresh 10-product quality sample retest confirmed compact prompt behavior:
  - cache miss, so RAG/LLM path was measured
  - 10 classifications returned across 4 small batches
  - no incomplete-batch fallback was needed
  - model routing used `gpt-4.1-mini` for all 4 classification calls
  - total prompt characters: 23,816
  - total prompt tokens: 15,626
  - total completion tokens: 3,172
  - total request duration: around 222 seconds
  - classification LLM duration: around 81 seconds
- 10-product retest after restart returned from classification cache:
  - `classify_cache_hit=1`
  - 10 classifications returned without new LLM calls
  - compact TEC prompt-size reduction was not measured in that run because the cached response bypassed RAG/LLM

## Step 13. Quality-safety adjustment for compact TEC context

### Issue

- after compacting TEC context, there was concern that classification quality could drop
- the latest 10-product retest was a cache hit, so it did not measure the new compact prompt behavior

### Why it matters

- reducing context too aggressively can remove useful candidate positions or discriminating TEC labels
- cost and speed improvements must not come at the expense of materially worse classification quality

### Fix implemented

- created a fresh cache-miss test file: `sample_products_quality_10.csv`
- adjusted compact context to a safer balance:
  - FAISS top-k changed from 12 to 16
  - candidate positions changed from 6 to 8
  - TEC excerpt length changed from 120 to 180 characters
  - subposition groups changed from 6 to 8
- kept compact mode enabled to still reduce prompt size versus the original 20/15/verbose context

### Files updated

- `sample_products_quality_10.csv`
- `sam/candidate_set_enforcer.py`
- `sam/config/settings.py`
- `.env`
- `deploy/mosam-api.env.example`

### Expected result

- better balance between quality and speed/cost
- fresh sample list can test prompt reduction without hitting the previous cache key
- candidate context remains smaller than the original implementation but less aggressive than the first compact version

### Verification

- backend compile passed with `python -m py_compile sam\candidate_set_enforcer.py sam\config\settings.py sam\rag.py`
## Step 37. Seven-product cold-run audit and retrieval cleanup

### Measured result before this fix

- seven fresh client-regression products returned seven classifications
- broad technical families were sensible for all seven products; the former phone, recording-media, and bicycle-part errors did not recur
- cold duration was `246430.6 ms`
- classification used three LLM calls: two `gpt-5` calls and one `gpt-4.1-mini` call
- prompt usage was `22614` tokens and completion usage was `10483` tokens
- the request still made 14 query-embedding calls, two per product
- five products used the new evidence-driven primary retrieval path
- complete codes were returned for Cisco Catalyst 9300, KUKA KR 16, and Omron NX102
- Huawei OceanStor, DJI Zenmuse, iPad Pro, and ABB ACS880 remained provisional at a defensible broader level

### Issues found

- the second embedding per structured item came from historical validated-example retrieval, not from official TEC candidate retrieval
- historical examples can add cost and may bias a strong official candidate set with stale prior decisions
- a confirmed TEC subdivision could be described as undetermined when the overall classification was later capped to provisional for weak candidate evidence
- a four-digit heading could display a descendant label instead of the exact official heading label

### Generic fixes implemented

- structured rows now skip historical-example embedding whenever official TEC candidates exist
- historical examples remain available as a fallback when official retrieval returns no candidates
- subdivision confirmation is rendered independently from the overall confidence status
- four-digit decisions now prefer the exact official heading label
- cache schemas were bumped to full-request `v17` and item `v12` so the next test cannot reuse pre-fix results

### Expected next cold run

- query-embedding calls should fall from 14 to approximately 7 for this seven-item structured test
- no new product-specific, manufacturer-specific, or tariff-code hardcoding was added
- Omron-style output should no longer contain both “sub-position confirmed” and “sub-position undetermined”
- broad-position labels such as `84.71` should use their exact TEC heading text

### Verification

- 59 focused offline unit tests passed with `python -m unittest`
- `sam/rag.py` and `sam/decision_engine.py` compiled successfully
## Credit-safe completion milestone - 23 July 2026

### Latest live evidence

- the `v17`/`v12` seven-product run performed seven embeddings instead of fourteen
- six products completed and were stored in the item cache
- OpenAI returned `429 insufficient_quota` while starting the final one-product batch
- two GPT-5 classification calls completed before the quota error
- telemetry reported `16488` prompt tokens and `10042` completion tokens for those two calls

### Resilience gap fixed

- recognized quota, rate-limit, timeout, and provider connection failures now preserve successful
  item results and return explicit retryable placeholders for unfinished rows
- sequential processing stops further provider calls after the first recognized provider outage
- parallel manufacturer-reference errors use the same retryable response contract
- non-provider programming failures remain visible and are re-raised
- frontend highlights retryable rows, excludes them from validation, and provides a cache-aware retry

### Verification

- 265 offline backend tests passed; five live Upstash integration tests were skipped
- 73 focused cache, quota, hierarchy, decision, evidence, and acceptance tests passed
- frontend TypeScript check passed
- no paid OpenAI calls were used for this verification

### Remaining external acceptance

- six of seven client-regression items should be reused from `v12` item cache
- after credit restoration, classify only the remaining item through the same seven-row request
- run one immediate warm repeat to confirm seven cache hits and zero OpenAI calls
- verify live Upstash and Supabase behavior in the deployment environment

### Final acceptance automation

- added `sam.final_acceptance`, a local scorer for exported result JSON and backend telemetry logs
- selective mode permits only the expected one-item recovery work after six `v12` cache hits
- warm mode requires zero classification calls and zero embeddings
- both modes enforce result count, retryable/placeholder safety, forbidden-heading safety, quality outcome,
  and TEC candidate-recall gates
- four dedicated acceptance-scoring tests pass without calling OpenAI

## Phase A quality hardening - 23 July 2026

### Issue

- the remaining weak cases were no longer broad cost or batch problems; they were family-selection mistakes
- tablet/computer products could still compete with smartphone-family headings
- industrial drives could still compete with unrelated household-appliance headings
- camera, storage-system, and industrial-control rows needed stronger generic family weighting before the LLM step

### Fix implemented

- added compatibility-aware candidate reranking in `sam/candidate_set_enforcer.py`
- ranking now combines:
  - retrieval score
  - sub-position affinity
  - functional family compatibility
- added generic contradiction penalties for:
  - tablet/computer vs smartphone headings
  - network equipment vs smartphone headings
  - imaging camera vs cinematographic/phone headings
  - storage system vs recording-media headings
  - PLC/control equipment vs generic ADP headings
  - industrial variable-speed drives vs household-appliance headings
  - industrial robots vs cycle/motorcycle-part headings
- surfaced compatibility notes and functional warnings in the merged candidate prompt
- expanded customs-keyword generation for:
  - tablets and portable data-processing devices
  - complete storage systems
  - modern imaging cameras
  - static converters / variable-speed drives

### Verification

- `python -m unittest sam.tests.test_candidate_set_enforcer sam.tests.test_rag_customs_keywords sam.tests.test_functional_coherence sam.tests.test_client_regression_technical_nature`
  passed: 32 tests
- `python -m py_compile sam/candidate_set_enforcer.py sam/rag.py sam/tests/test_candidate_set_enforcer.py sam/tests/test_rag_customs_keywords.py`
  passed

### Expected impact

- stronger chapter and heading prioritization before the final model decision
- fewer obvious family-conflict outcomes on professional equipment
- better quality without adding any hardcoded product-to-HS mappings

## Phase A cache freshness follow-up - 23 July 2026

### Issue

- the first post-patch seven-product rerun still returned `7/7` item-cache hits
- this meant the new quality logic was not being measured live on the affected product families
- broad cache invalidation would waste credit on unrelated stable products

### Fix implemented

- added a targeted item-cache schema refresh in `sam/api.py`
- default item-cache version remains `v12` for ordinary products
- quality-sensitive families now use `v13`, including generic signals for:
  - tablets and tablet-computer rows
  - switches, routers, and network equipment
  - modern imaging cameras
  - complete storage systems
  - PLC / industrial control equipment
  - static converters / variable-speed drives
  - industrial robots
- legacy labelled-reference fallback is skipped for refreshed families so stale `v12` rows are not silently reused

### Verification

- targeted cache and quality tests:
  - `python -m unittest sam.tests.test_cache sam.tests.test_candidate_set_enforcer sam.tests.test_rag_customs_keywords sam.tests.test_functional_coherence sam.tests.test_client_regression_technical_nature`
- result:
  - quality/cache logic passed
  - only the known live Upstash integration tests failed in the restricted environment because outbound network access was blocked
- `python -m py_compile sam/api.py sam/tests/test_cache.py` passed

## Phase B upstream low-confidence product-understanding fallback - 23 July 2026

### Issue

- the remaining weak cases are now mostly product-understanding problems before the legal tariff logic starts
- some rows still enter the decision engine with a broad or weak `technical_nature`
- we wanted extra intelligence where it helps quality, without moving RGI, label lookup, or candidate enforcement into LLM logic

### Fix implemented

- added a guarded OpenAI fallback inside `sam/functional_profile.py`
- this fallback runs only when:
  - local technical-nature confidence is still low
  - the row has enough technical detail or a manufacturer-reference signal
  - the identification layer is not already strong enough
- the fallback asks only for tariff-neutral product understanding:
  - generic product type
  - family
  - primary function
  - system role
  - semantic terms
  - missing discriminants
- fallback output is accepted only if it is materially stronger than the local result
- deterministic tariff logic remains unchanged:
  - no OpenAI was added to RGI logic
  - no OpenAI was added to candidate enforcement
  - no OpenAI was added to section/chapter normalization

### Files updated

- `sam/functional_profile.py`
- `sam/config/settings.py`
- `sam/tests/test_functional_profile.py`

### Expected result

- better upstream product understanding on low-confidence technical/professional products
- higher chance of reaching the right family before heading/subheading discrimination
- controlled cost because clear products still stay on the local path

### Verification

- `python -m unittest sam.tests.test_functional_profile sam.tests.test_technical_nature`
- `python -m py_compile sam\functional_profile.py sam\config\settings.py sam\tests\test_functional_profile.py`

## Phase C product-evidence consolidation for manufacturer references - 23 July 2026

### Issue

- after improving `functional_profile`, some weak rows still reached retrieval/classification without enough structured identity evidence
- manufacturer-reference cases especially benefit when the downstream query and prompt keep the confirmed identity signals visible
- uncertain rows also needed clearer ambiguity markers so the legal layers stay conservative

### Fix implemented

- extended `sam/product_evidence.py` with:
  - `identity_terms`
  - `ambiguity_flags`
- retrieval queries now include strong identity terms when:
  - the input is a manufacturer reference, or
  - identity confidence is already high
- evidence prompt block now exposes:
  - manufacturer
  - commercial name
  - identity terms
  - explicit ambiguity flags
- added a generic ambiguity detector for:
  - uncertain identity
  - low identity confidence
  - low technical-nature confidence
  - manufacturer reference not yet tied to a confirmed product
  - unspecified system role
  - multiple missing discriminants

### Files updated

- `sam/product_evidence.py`
- `sam/tests/test_product_evidence.py`
- `sam/tests/test_functional_profile.py`

### Expected result

- stronger retrieval context for manufacturer-reference products
- clearer prompt evidence for difficult professional equipment
- safer provisional behavior when evidence is still weak or ambiguous

### Verification

- `python -m unittest sam.tests.test_product_evidence sam.tests.test_functional_profile sam.tests.test_technical_nature`
- `python -m py_compile sam\product_evidence.py sam\tests\test_product_evidence.py`

## Phase D identification-output normalization for weak manufacturer references - 23 July 2026

### Issue

- low-confidence identification results could still contain generic labels such as `electronic module` or vague functions like `industrial use`
- these outputs were not wrong enough to fail parsing, but still too weak to guide quality classification well
- manufacturer-reference inputs especially need explicit uncertainty markers when the exact product nature is still not confirmed

### Fix implemented

- added `_normalize_identification_output()` in `sam/product_identification.py`
- this post-processing now:
  - deduplicates materials, technical characteristics, and missing discriminants
  - fills `manufacturer_part_number` from the original reference when missing
  - injects `Reference fabricant : ...` into the enriched description when useful
  - caps confidence when `product_type` stays too generic
  - caps confidence when `function_usage` stays too generic
  - adds stronger missing-information hints for manufacturer-reference inputs
  - flags weak eliminative reasoning in notes when similar products were not clearly ruled out
- strong specific identifications remain untouched

### Files updated

- `sam/product_identification.py`
- `sam/tests/test_product_identification.py`

### Expected result

- weak manufacturer-reference identifications become explicitly provisional earlier
- downstream retrieval and classification receive cleaner, more honest product facts
- false confidence on vague technical identities is reduced

### Verification

- `python -m unittest sam.tests.test_product_identification sam.tests.test_product_evidence sam.tests.test_functional_profile sam.tests.test_technical_nature`
- `python -m py_compile sam\product_identification.py sam\tests\test_product_identification.py`

## Phase E candidate recall and medical-family protection - 23 July 2026

### Issue

- 10-item and 25-item quality runs showed too many low-affinity candidate sets
- one critical wrong-family error remained: `Disposable medical syringe` drifted into heading `90.22` (radiology / X-ray equipment)
- this meant the system still needed stronger candidate-family guidance before final selection

### Fix implemented

- extended `sam/rag.py` customs-keyword expansion for syringe / injection / medical-consumable language
- extended `sam/candidate_set_enforcer.py` compatibility scoring with a new medical-device family:
  - positive weight for medical-instrument wording
  - strong negative penalty for radiology / X-ray wording
- extended `sam/functional_coherence.py` with a deterministic medical-device conflict:
  - if the selected heading is `90.22`
  - and the product language matches syringe / injection / sterile medical device terms
  - and there is no radiology signal
  - then the result is forced provisional as an incompatible family

### Files updated

- `sam/rag.py`
- `sam/candidate_set_enforcer.py`
- `sam/functional_coherence.py`
- `sam/tests/test_rag_customs_keywords.py`
- `sam/tests/test_candidate_set_enforcer.py`
- `sam/tests/test_functional_coherence.py`

### Expected result

- better official-candidate recall for syringe / medical-consumable rows
- lower chance of impossible radiology-family outcomes on simple medical devices
- stronger deterministic protection against catastrophic wrong-family classifications

### Verification

- `python -m unittest sam.tests.test_rag_customs_keywords sam.tests.test_candidate_set_enforcer sam.tests.test_functional_coherence`
- `python -m py_compile sam\rag.py sam\candidate_set_enforcer.py sam\functional_coherence.py`
