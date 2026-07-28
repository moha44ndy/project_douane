# Mosam Final Delivery Plan

## Purpose

This document turns the remaining wrap-up work into a delivery checklist.

It separates:

- implementation work that is already completed
- delivery-safety controls that must be present before handover
- external validation steps that still depend on live services, credit, or client review

## Delivery objective

Deliver the current Mosam improvement scope as a stable, documented, cost-controlled classification assistant,
without over-claiming universal customs accuracy.

## Remaining work plan

### Phase R1. Delivery-safety guardrails

#### Goal

Ensure no weak or incomplete result can be handed over without being clearly marked and explained.

#### Required outcomes

- no blank or placeholder `hs_code` in the final acceptance export
- no confirmed blank/placeholder result
- every provisional row includes a human-readable explanation
- retryable rows are rejected by the release gate

#### Status

Completed.

#### Delivered implementation

- missing-code recovery already keeps a compatible heading provisionally instead of leaving an empty code
- final acceptance now fails when a provisional row has no explanation
- final acceptance already rejects retryable rows and placeholders

## Phase R2. Delivery documentation alignment

#### Goal

Prepare one clean client-facing handover document and one internal delivery-readiness reference.

#### Required outcomes

- client document explains what was improved
- scope boundaries remain explicit
- known limitations are stated honestly
- final validation process is documented

#### Status

Completed.

#### Delivered implementation

- `CLIENT_CHANGE_SUMMARY.md` remains the single client-facing change document
- `CLIENT_DELIVERY_PROPOSAL.md` remains the scope-reference document
- this file records internal delivery readiness and remaining external validation

## Phase R3. Internal release gate

#### Goal

Make final delivery depend on measurable acceptance conditions instead of ad-hoc judgment.

#### Required outcomes

- offline acceptance script available
- selective run gate documented
- warm repeat gate documented
- benchmark quality floor documented

#### Status

Completed, pending live execution in the deployment environment.

#### Delivered implementation

- `sam.final_acceptance` scores final artifacts without making OpenAI requests
- acceptance checks include:
  - result count
  - no retryable rows
  - no placeholders
  - no confirmed placeholders
  - provisional rows explained
  - no forbidden headings
  - minimum quality outcomes
  - minimum candidate recall
  - cache/LLM/embedding budget checks

## What is already completed

- API cost optimization through caching, routing, and gating
- response-time improvement through batching and cache fast paths
- multi-product stability and row integrity
- frontend data preservation in backend output
- manufacturer-reference identification flow with controlled external search
- CSV/Excel import and template flow
- frontend numeric validation
- progress visibility
- backend logs and telemetry
- generic quality reinforcement for network, PLC, VFD, robot, compute, storage, tablet, and mixed-display families

## What is not an implementation blocker anymore

The following items are not code-completion blockers for delivery:

- full 25-product or 40-product paid reruns after every edit
- a full deterministic legal rule engine for all tariff categories
- a complete global manufacturer/part-number database
- guaranteed final customs-grade classification for every edge case

## External validation still required

These steps are still required before calling the delivery fully accepted in production:

1. run the bounded live selective acceptance flow
2. run the immediate warm repeat acceptance flow
3. preserve exported JSON and backend log artifacts
4. confirm live cache/database behavior in the deployment environment
5. complete client or customs-expert review for ambiguous professional-equipment outputs

## Recommended handover package

1. updated backend code
2. updated frontend code
3. `CLIENT_CHANGE_SUMMARY.md`
4. deployment/config instructions
5. acceptance artifacts from the final selective and warm runs

## Final delivery statement

The implementation scope is complete enough for delivery as a current-scope final handover.

The only remaining items are live acceptance execution and domain-review confirmation, not core engineering build work.
