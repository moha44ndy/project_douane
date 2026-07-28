# Mosam Technical Change Document

## Purpose

This document explains the technical changes made in the Mosam project in a practical engineering format:

- what the system was doing before
- what it is doing now
- why the change was needed
- which files were updated to support that behavior

This is not a generic project overview only.  
It is a technical handover document focused on the implemented changes.

## 1. System Context

Mosam is a CEDEAO/TEC tariff-classification assistant.  
It takes product input from the frontend, processes it in the backend, retrieves relevant customs context from indexed tariff content, asks the model to classify within that context, and then applies local validation and formatting before returning the final result.

The important architectural point is:

**Mosam is a pipeline, not a single prompt.**

The main stages are:

1. structured input collection
2. optional product identification
3. evidence building
4. RAG retrieval from official tariff content
5. candidate heading control
6. LLM classification
7. local completeness/coherence/subposition checks
8. final response assembly

## 2. Change Format

Each section below follows this logic:

- **Before**: what the system was doing earlier
- **Now**: what the system does after the implementation
- **Why changed**: the technical reason behind the change
- **Files changed**: main files involved in that improvement

## 3. Cost and Reuse Control

### Before

- repeated products could be classified again from scratch
- multi-product requests could trigger unnecessary repeated OpenAI work
- fallback processing could increase cost because successful row-level work was not reused strongly enough

### Now

- full-request cache is used for repeated identical requests
- item-level classification cache is used for repeated product rows
- product-identification cache is used for repeated manufacturer-reference lookups
- only missing or uncached rows are processed again

### Why changed

The first major client concern was API cost.  
The cost problem was not only model choice; it was also repeated processing of the same work.

### Files changed

- [api.py](D:/Xavinex/project_douane%20-%20Copy/sam/api.py)
- [cache.py](D:/Xavinex/project_douane%20-%20Copy/sam/cache.py)
- [settings.py](D:/Xavinex/project_douane%20-%20Copy/sam/config/settings.py)
- [test_cache.py](D:/Xavinex/project_douane%20-%20Copy/sam/tests/test_cache.py)

## 4. Batch Processing and Multi-Product Stability

### Before

- large structured submissions could behave like one heavy operation
- one weak product could negatively affect the whole request
- some responses could return fewer output rows than submitted rows
- partial failures were harder to recover safely

### Now

- structured rows are processed in smaller controlled batches
- row integrity is protected more strongly
- missing rows can be recovered with targeted fallback logic
- successful rows are preserved even when other rows fail
- retryable rows are returned explicitly instead of silently disappearing

### Why changed

The client reported unstable batch behavior and incomplete output.  
This was an orchestration and recovery problem, not only an LLM problem.

### Files changed

- [api.py](D:/Xavinex/project_douane%20-%20Copy/sam/api.py)
- [classification_progress.py](D:/Xavinex/project_douane%20-%20Copy/sam/classification_progress.py)
- [decision_engine.py](D:/Xavinex/project_douane%20-%20Copy/sam/decision_engine.py)
- [classification_completeness.py](D:/Xavinex/project_douane%20-%20Copy/sam/classification_completeness.py)
- [test_classification_completeness.py](D:/Xavinex/project_douane%20-%20Copy/sam/tests/test_classification_completeness.py)

## 5. Product Identification and Manufacturer References

### Before

- short references and part numbers could enter the classification flow without a strong product identity
- the system could try to classify a code-like input before understanding what product it referred to
- external identification was not bounded enough for cost-sensitive use

### Now

- the system detects likely manufacturer-reference inputs
- it can enrich those inputs with product identity before tariff classification
- manufacturer reference, product family, and likely function are preserved as evidence
- external search is used in a more controlled way
- uncertain identification remains marked as uncertain

### Why changed

This was one of the most important real-world usage problems reported by the client.  
Transit users often know the reference and invoice value, not the full commercial description.

### Files changed

- [product_identification.py](D:/Xavinex/project_douane%20-%20Copy/sam/product_identification.py)
- [openai_web_search.py](D:/Xavinex/project_douane%20-%20Copy/sam/openai_web_search.py)
- [functional_profile.py](D:/Xavinex/project_douane%20-%20Copy/sam/functional_profile.py)
- [product_evidence.py](D:/Xavinex/project_douane%20-%20Copy/sam/product_evidence.py)
- [test_product_identification.py](D:/Xavinex/project_douane%20-%20Copy/sam/tests/test_product_identification.py)
- [test_web_search_pipeline.py](D:/Xavinex/project_douane%20-%20Copy/sam/tests/test_web_search_pipeline.py)

## 6. Technical Nature and Product Understanding

### Before

- classification relied too heavily on raw product text and generic wording
- the system did not always create a strong tariff-neutral understanding of what the product technically was
- this made retrieval weaker for advanced equipment

### Now

- the system builds a structured functional profile
- it infers a technical nature such as:
  - network equipment
  - optical transceiver
  - storage system
  - storage device
  - accelerator card
  - server
  - industrial controller
  - static converter / drive
  - robot
  - tablet / hybrid computer
  - mixed-reality headset
- this profile is then used to guide retrieval and candidate ranking

### Why changed

If the system does not first understand what kind of product it is looking at, RAG can still retrieve related but wrong headings and the model can still drift into the wrong family.

### Files changed

- [functional_profile.py](D:/Xavinex/project_douane%20-%20Copy/sam/functional_profile.py)
- [technical_nature.py](D:/Xavinex/project_douane%20-%20Copy/sam/technical_nature.py)
- [product_evidence.py](D:/Xavinex/project_douane%20-%20Copy/sam/product_evidence.py)
- [test_functional_coherence.py](D:/Xavinex/project_douane%20-%20Copy/sam/tests/test_functional_coherence.py)

## 7. RAG Retrieval and Tariff Candidate Control

### Before

- retrieval was more dependent on generic query wording
- weak lexical similarity could still promote the wrong heading family
- the model had less structured control over which official headings should be preferred

### Now

- retrieval uses richer evidence built from product type, function, family, and structured row content
- official TEC candidates are gathered and reranked before the final LLM step
- candidate sets preserve credible chapter diversity
- heading hints and customs keywords help retrieval for difficult product families
- the LLM sees a more bounded candidate space instead of a looser context

### Why changed

The system needed to move from “retrieve something similar” toward “retrieve and control the most defensible customs families”.

This is where RAG, tariff labels, and candidate enforcement now work together.

### Files changed

- [rag.py](D:/Xavinex/project_douane%20-%20Copy/sam/rag.py)
- [candidate_set_enforcer.py](D:/Xavinex/project_douane%20-%20Copy/sam/candidate_set_enforcer.py)
- [tariff_labels.py](D:/Xavinex/project_douane%20-%20Copy/sam/tariff_labels.py)
- [test_candidate_set_enforcer.py](D:/Xavinex/project_douane%20-%20Copy/sam/tests/test_candidate_set_enforcer.py)
- [test_tariff_labels.py](D:/Xavinex/project_douane%20-%20Copy/sam/tests/test_tariff_labels.py)

## 8. Wrong-Family Result Protection

### Before

- some results could remain too confident even when they were semantically incompatible with the product function
- a result could look syntactically valid while still belonging to the wrong product family

### Now

- the system checks functional coherence after selection
- weak or incompatible results are downgraded to provisional
- confidence is capped when evidence is weak
- clearly missing code situations can recover a safer heading-level result instead of staying blank

### Why changed

The client’s biggest quality concern was not only incomplete classification.  
It was wrong-family classification, which is more dangerous because it can look convincing.

### Files changed

- [functional_coherence.py](D:/Xavinex/project_douane%20-%20Copy/sam/functional_coherence.py)
- [classification_completeness.py](D:/Xavinex/project_douane%20-%20Copy/sam/classification_completeness.py)
- [candidate_set_enforcer.py](D:/Xavinex/project_douane%20-%20Copy/sam/candidate_set_enforcer.py)
- [decision_engine.py](D:/Xavinex/project_douane%20-%20Copy/sam/decision_engine.py)
- [test_decision_engine.py](D:/Xavinex/project_douane%20-%20Copy/sam/tests/test_decision_engine.py)

## 9. Subposition and Heading-Level Safety

### Before

- the system could struggle when exact subposition criteria were missing
- some outputs could become too broad, too empty, or too weakly explained

### Now

- subposition resolution is handled more explicitly
- the system can stop at the last justifiable tariff level
- missing criteria are explained more clearly
- blank-code behavior is better controlled

### Why changed

In customs work, false precision is risky.  
It is better to stop at a justified heading and mark the row provisional than to invent a precise subheading without enough criteria.

### Files changed

- [tariff_subposition.py](D:/Xavinex/project_douane%20-%20Copy/sam/tariff_subposition.py)
- [position_validator.py](D:/Xavinex/project_douane%20-%20Copy/sam/position_validator.py)
- [test_tariff_subposition.py](D:/Xavinex/project_douane%20-%20Copy/sam/tests/test_tariff_subposition.py)
- [test_position_validator.py](D:/Xavinex/project_douane%20-%20Copy/sam/tests/test_position_validator.py)

## 10. Frontend Structured Input and Data Preservation

### Before

- the frontend collected useful fields, but backend preservation was not always strong enough
- quantity and value validation were too soft
- import workflows were not practical enough

### Now

- the frontend sends cleaner structured product rows
- numeric fields are validated more strictly
- imported CSV/Excel rows can populate the main merchandise table
- important business fields are preserved through the backend flow

### Why changed

Good classification depends on good input, and user-entered commercial data should not disappear between entry and result display.

### Files changed

- [MerchandiseTableForm.tsx](D:/Xavinex/project_douane%20-%20Copy/frontend/src/components/MerchandiseTableForm.tsx)
- [merchandiseQuery.ts](D:/Xavinex/project_douane%20-%20Copy/frontend/src/lib/merchandiseQuery.ts)
- [page.tsx](D:/Xavinex/project_douane%20-%20Copy/frontend/src/app/page.tsx)
- [api.py](D:/Xavinex/project_douane%20-%20Copy/sam/api.py)

## 11. Import Workflow

### Before

- manual entry was too slow for multiple products
- import flow was not ready for stable operational use

### Now

- CSV/Excel import is supported
- multilingual header matching is supported
- a template is available for users
- imported rows remain editable before classification

### Why changed

The client wanted a practical way to load multiple product rows without retyping everything manually.

### Files changed

- [MerchandiseTableForm.tsx](D:/Xavinex/project_douane%20-%20Copy/frontend/src/components/MerchandiseTableForm.tsx)
- [api.py](D:/Xavinex/project_douane%20-%20Copy/sam/api.py)
- [deploy/mosam-api.env.example](D:/Xavinex/project_douane%20-%20Copy/deploy/mosam-api.env.example)

## 12. Progress Visibility and Operational Feedback

### Before

- long runs looked like a passive wait
- the user could not clearly see whether identification, batch processing, fallback, or final report generation was happening

### Now

- progress steps are streamed and rendered in the frontend
- users can see where the request is inside the pipeline

### Why changed

This improves trust, testing visibility, and user experience during longer operations.

### Files changed

- [classificationStream.ts](D:/Xavinex/project_douane%20-%20Copy/frontend/src/lib/classificationStream.ts)
- [ClassificationProgressPanel.tsx](D:/Xavinex/project_douane%20-%20Copy/frontend/src/components/ClassificationProgressPanel.tsx)
- [classification_progress.py](D:/Xavinex/project_douane%20-%20Copy/sam/classification_progress.py)

## 13. Logs, Telemetry, and Final Acceptance

### Before

- debugging cost, time, cache, and fallback behavior was harder
- final acceptance depended too much on visual checking

### Now

- request-level logs are clearer
- cache hits/misses and model usage are visible
- final acceptance rules are codified
- retryable rows, placeholders, and unexplained provisional rows are now easier to detect and block

### Why changed

The system needed better observability and a more defensible release gate.

### Files changed

- [api.py](D:/Xavinex/project_douane%20-%20Copy/sam/api.py)
- [final_acceptance.py](D:/Xavinex/project_douane%20-%20Copy/sam/final_acceptance.py)
- [test_final_acceptance.py](D:/Xavinex/project_douane%20-%20Copy/sam/tests/test_final_acceptance.py)

## 14. What the System Is Doing Now, Technically

After the implementation, Mosam is no longer just:

- “take description”
- “search customs document”
- “ask model for answer”

Now it is doing this:

- structuring input
- understanding product nature
- enriching weak reference-style input
- retrieving bounded official tariff candidates
- reranking candidates using product-family logic
- guiding the LLM with controlled customs context
- downgrading weak or contradictory outcomes
- preserving user business data
- reusing work through caching
- exposing telemetry for optimization and acceptance

## 15. Scope Boundary

This does **not** mean the project is now:

- a full deterministic customs decision-tree engine
- a complete global part-number database
- a universal OCR engine for all invoice documents
- a guaranteed official customs authority for all goods

What it **does** mean is:

the current architecture has been significantly strengthened in the exact areas that were causing the client’s operational pain.

## 16. Final Technical Position

The most accurate technical way to describe the delivered work is:

**We changed Mosam from a looser prompt-led classification flow into a more structured, evidence-driven, candidate-controlled customs-assistance pipeline.**

That is the main technical meaning of the implementation.
