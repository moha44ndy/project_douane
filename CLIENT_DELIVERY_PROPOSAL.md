# Mosam Classification System - Client Improvement Scope

## 1. Purpose

This document explains the improvement scope we will deliver for the Mosam CEDEAO tariff classification system.

The purpose is to clearly define:

- the issues identified by the client
- what we will fix in the current delivery
- to what level we will improve each area
- what is excluded from the current scope
- what the final deliverables will contain

## 2. Client Issues Identified

Based on the client discussion and technical review, the main issues are:

1. API cost is too high, especially when more than one product is classified.
2. Response time is too slow for practical business use.
3. Classification results are not good enough in some cases.
4. Multi-product classification is unstable and may return incomplete output.
5. Frontend product fields are not being fully utilized by the backend.
6. Manufacturer references and part numbers should be identified using external product search when possible.
7. Spreadsheet import is needed so users can upload multiple product rows easily.
8. Users need clearer visibility during long classification runs.
9. Backend logs need to be clearer for debugging and future optimization.

## 3. Delivery Goal

The goal of this delivery is to make the current system more usable, more stable, and more cost-controlled without rebuilding the full classification engine from zero.

We will focus on:

- reducing avoidable OpenAI/API calls
- improving multi-product processing
- improving manufacturer-reference identification through internet-based search
- preserving frontend product information
- improving batch stability
- adding spreadsheet import support
- improving user progress visibility
- documenting the changes clearly

This delivery will improve the existing product architecture and prepare it for deeper future enhancements.

## 4. What We Will Deliver

### 4.1 API Cost Optimization

#### Current problem

The system can become expensive because multi-product requests may be processed as a large AI prompt. If the model output is incomplete, the backend may run additional fallback calls for each product.

#### What we will implement

- Add caching for single-product classification results.
- Reuse cached product classifications during fallback processing.
- Split large structured table submissions into smaller configurable batches.
- Add a batch-size configuration using `MOSAM_STRUCTURED_FORM_BATCH_SIZE`.
- Add model-routing configuration so cheaper models can be used for simpler cases where appropriate.
- Reduce unnecessary product-identification and web-search calls using gating rules.
- Reduce oversized TEC context in prompts while keeping candidate-position controls in place.

#### Improvement level we will provide

We will reduce avoidable repeated API usage and make multi-product cost more controlled.

This will not guarantee a fixed exact price per product, because final API cost depends on:

- selected model
- input length
- number of products
- fallback frequency
- whether product identification or web search is enabled

#### Expected end result

- Lower repeated API calls.
- Lower cost risk for multi-product submissions.
- Better cost control through configuration.
- Easier future measurement of cost per request.

## 5. Response Time Optimization

### Current problem

Large prompts and fallback calls can make classification take too long.

### What we will implement

- Process structured table rows in smaller batches instead of one very large prompt.
- Avoid full reprocessing when only some rows fail.
- Reuse cache for repeated products.
- Compact the TEC candidate context sent to the model where safe.
- Add progress updates so the user can see what is happening during the wait.

### Improvement level we will provide

We will improve normal multi-product response behavior and reduce avoidable long waits.

This does not mean every classification will become instant. Some complex products may still take longer because the system must retrieve tariff context and generate a careful classification response.

### Expected end result

- Better response behavior for normal product lists.
- Less risk of very long delays caused by one failed large batch.
- Better user experience during long-running classification.

## 6. Classification Result Stability

### Current problem

The system may return fewer classifications than the number of submitted products. For example, 10 submitted products may return only 1 classification.

### What we will implement

- Add row-count integrity checks.
- Preserve one output row per structured frontend product row.
- Recover missing rows using targeted fallback classification.
- Prevent structured frontend rows from being collapsed by duplicate-merge logic.
- Preserve and merge product metadata into the final result.

Metadata to preserve:

- designation
- material/composition
- usage
- characteristics
- quantity
- unit
- country of origin
- value
- currency

### Improvement level we will provide

We will improve result completeness and row-level stability for structured table submissions.

This improves output consistency, but it does not fully solve every possible classification accuracy issue.

### Expected end result

- Multi-product submissions should return results aligned with submitted rows.
- Missing-row cases should be recovered more safely.
- User-entered business data should remain visible in the final output.

## 7. Classification Quality Improvement

### Current problem

The client reported that some classification results are not good enough.

### What we will implement in this delivery

- Improve how structured product details are passed into the backend.
- Improve how product metadata is merged into final classification results.
- Improve fallback behavior when batch output is incomplete.
- Add stricter frontend validation for quantity and value.
- Keep existing RGI/completeness/risk enrichment flow integrated with the output.
- Add a repeatable 25-product quality benchmark at HS6, heading, and chapter level.
- Prevent weak retrieval candidates or validators from blindly overriding a more coherent classification.
- Add targeted customs terminology for product groups where normal commercial wording retrieves the wrong TEC heading.
- Migrate deleted legacy ceramic heading `69.08` to current HS 2022 heading `69.07`.
- Resolve ceramic tile subheadings deterministically when the water-absorption percentage is provided.

### Improvement level we will provide

We will improve classification quality within the current architecture by giving the backend cleaner and richer product data, and by preventing incomplete multi-product output.

### What is not included in this delivery

A full deterministic customs classification engine is not included in this scope.

That means this delivery will not fully implement:

- complete CEDEAO/TEC decision-tree classifier
- full chapter-to-heading-to-subheading-to-national-line rule engine
- official legal-rule validation for every possible product category
- guaranteed customs-grade final classification for all edge cases

### Expected end result

- Better quality than the current system for structured and multi-product inputs.
- Better consistency for repeated product types.
- Stronger foundation for a future rule-based classifier.

## 8. Manufacturer Reference and External Product Search

### Current problem

The client may enter a manufacturer reference, commercial reference, or part number instead of a normal product description.

Example inputs can include:

- manufacturer part numbers
- model references
- industrial component references
- commercial product codes
- short technical references

The system should not depend on a manually maintained complete manufacturer database, because it is not realistic to collect and maintain all products that exist in the market.

### What we will implement

We will improve the product-identification flow so that when the input looks like a manufacturer reference or part number, the system will try to identify the product using external internet-based search.

The improved flow will:

- detect whether the input looks like a manufacturer reference or part number
- use external product search when the reference needs identification
- try to identify the product name, type, manufacturer, function, and use
- pass the enriched product description into the tariff-classification flow
- keep the original user reference attached to the result
- include web-search/source information when available
- mark the identification as uncertain if the reference cannot be confirmed reliably

### Improvement level we will provide

We will improve manufacturer-reference handling by making the system attempt external product identification before tariff classification.

This means that if the user enters a reference, the system will try to understand what product that reference represents, instead of classifying only the raw code.

### What we will not provide

We will not build or maintain a complete manufacturer/part-number database.

We will also not guarantee that every reference can be identified, because some references may be:

- private/internal supplier codes
- discontinued products
- ambiguous across multiple manufacturers
- unavailable online
- too generic or too short

### Expected end result

- Better handling of manufacturer references than the current flow.
- Improved ability to identify external products from public information.
- Less dependence on manual database maintenance.
- More transparent output when identification is uncertain.
- Better classification input when the external product can be identified.

## 9. Frontend Data Utilization

### Current problem

The frontend collects useful product fields, but those fields must be properly sent, processed, and preserved by the backend.

### What we will implement

- Ensure structured frontend rows are sent to the backend.
- Build richer backend product dossiers from frontend row data.
- Preserve commercial fields in the final response.
- Add strict numeric validation for quantity and value.

### Improvement level we will provide

We will make the current frontend table data meaningfully useful for classification and final result display.

### Expected end result

- Less loss of user-entered information.
- Cleaner backend input.
- Better final result context.

## 10. Excel/CSV Import

### Current problem

Manual entry is slow for users who need to classify multiple products.

### What we will implement

- Add CSV/Excel import into the frontend merchandise table.
- Add backend parsing endpoint for spreadsheet import.
- Add header matching for expected product fields.
- Add downloadable CSV template.

Supported import target fields:

- designation
- material/composition
- usage
- characteristics
- quantity
- unit
- country of origin
- value
- currency

### Improvement level we will provide

We will support structured CSV/Excel import into the table.

### What is not included in this delivery

Complex invoice automation is not included in this scope.

This means the current delivery will not fully support:

- OCR for scanned invoices
- complex PDF invoice table extraction
- all supplier invoice layouts
- automatic line-item extraction from every Word/PDF format
- background queue for very large document processing

### Expected end result

- Users can import clean spreadsheet product lists.
- Imported rows can be reviewed/edited before classification.
- Spreadsheet import itself will not trigger AI cost.

## 11. User Progress Visibility

### Current problem

During long classification, the user does not clearly know what the system is doing.

### What we will implement

- Add backend progress events.
- Show frontend progress steps.
- Show operational details such as:
  - preparing products
  - classifying a batch
  - running fallback
  - merging final results

### Improvement level we will provide

We will improve visibility for the streaming classification flow.

### Expected end result

- Better user confidence during longer processing.
- Easier demo/testing experience.
- Better visibility when fallback is being used.

## 12. Backend Logging

### Current problem

Debugging cost, response time, and incomplete output is difficult without clear logs.

### What we will implement

- Add request summary logs.
- Add cache hit/miss logs.
- Add result summary logs.
- Add validation/bulk-validation logs.
- Add batch and fallback logs.
- Add request-level telemetry summary for:
  - model calls
  - cache behavior
  - fallback count
  - batch count
  - web-search usage
  - request duration

### Improvement level we will provide

We will provide operational logs sufficient for debugging current classification runs and comparing cost/time behavior before and after optimization.

### Expected end result

- Easier troubleshooting.
- Better visibility during client testing.
- Better foundation for cost and latency review.

## 13. Scope Removed or Deferred From Current Delivery

The following items are not included in the current delivery and should be treated as future enhancement scope:

### 13.1 Full manufacturer/part-number database

We will improve internet-based manufacturer-reference identification, but we will not deliver a complete manufacturer part-number database in this phase.

Reason:

The client does not want to maintain a complete database, and it is not realistic to collect every existing manufacturer product. The system will instead attempt to identify references through external product search when possible.

### 13.2 Full CEDEAO/TEC rule-based decision tree

We will improve the current classification pipeline, but we will not build a full deterministic rule engine in this phase.

Reason:

This is a larger customs-domain project requiring structured legal rules, test cases, validation, and expert review.

### 13.3 Full invoice OCR and complex document extraction

We will support structured CSV/Excel import, but we will not fully automate every invoice/PDF/Word layout in this phase.

Reason:

PDF invoices vary heavily and require OCR, table extraction, layout detection, and background processing.

### 13.4 Guaranteed final customs classification

The system will continue to provide indicative classification assistance.

Reason:

Official customs classification requires legal validation and domain authority review.

### 13.5 Exact cost guarantee

We will reduce avoidable cost and add controls, but we will not guarantee a fixed cost per product.

Reason:

Cost depends on model choice, prompt size, product complexity, fallback behavior, and provider pricing.

## 14. Alignment With Client Issues

| Client Issue | What We Will Do | Delivery Level |
|---|---|---|
| API cost too high | caching, batching, model-routing config, web-search gating | strong optimization within current architecture |
| Slow response time | smaller batches, fewer full fallback runs, progress visibility | strong practical improvement |
| Results not good | richer structured input, metadata preservation, fallback recovery | meaningful improvement, not full rule engine |
| Legacy or incomplete HS 2022 result | current-nomenclature migration and deterministic criteria where implemented | targeted rule-based improvement |
| Manufacturer references/part numbers | internet-based product identification before classification | included, without complete manual database |
| Multi-product instability | row integrity checks and targeted fallback | strong improvement |
| Frontend data not fully used | structured row payload and backend metadata merge | strong improvement |
| Spreadsheet import needed | CSV/Excel import and template | included |
| User does not know progress | live progress steps/details | included |
| Hard to debug | backend logs | included |

## 15. Final Deliverables

At the end of this delivery, we will provide:

1. Updated backend code.
2. Updated frontend code.
3. One client-facing change document explaining:
   - what issues were addressed
   - what was changed
   - why the changes were made
   - what improvement is expected
   - what remains outside the current scope

We will not provide multiple separate documentation files to the client. The client-facing documentation deliverable will be one change-summary document only.

The final document prepared for handover is `CLIENT_CHANGE_SUMMARY.md`. This proposal remains the pre-delivery scope reference and is not an additional client documentation deliverable.

## 16. Validation Plan

We will validate the delivery using:

- backend compile check
- frontend TypeScript check
- 10-product structured table test
- 25-product repeatable quality benchmark
- selective cold-cache and fully warm-cache comparison
- spreadsheet import test
- backend log review for batch/fallback behavior
- telemetry summary review for model-call count, fallback count, cache behavior, and duration
- manual comparison against previous behavior
- manufacturer-reference/web-search smoke test

Expected log indicator for optimized 10-product test:

`structured small-batch mode items=10 batch_size=3`

## 17. Expected Final Outcome

After this delivery, the client should receive a system that is:

- more cost-controlled
- faster for common multi-product workflows
- more stable for structured product rows
- better at preserving user-entered product data
- easier to use with CSV/Excel product lists
- clearer during long classification operations
- easier to debug and improve further

The system will still remain an assisted classification tool, not a fully official customs decision engine.
