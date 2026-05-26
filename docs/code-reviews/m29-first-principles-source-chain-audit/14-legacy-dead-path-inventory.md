# 14 Legacy Dead-Path Inventory

## Source Truth

Current product runtime is the upload-preview M29 mainline. Anything not imported by `backend/app/upload_preview/pipeline.py` or its stage functions is not active runtime, even if tests still exist.

Current active M29 mainline is documented in:

```text
AGENTS.md
docs/engineering/current-mainline-code-map.md
backend/app/upload_preview/pipeline.py
```

## Active Runtime Packages

These packages are part of current upload-preview execution:

```text
source_ui_physical_graph
region_relation_kernel / region_relation_graph_report
stable_design_cluster
m29_replay_plan
ownership_conservation
media_internal_decomposition
transparent_asset_report
m29_evidence_contract
internal_source_promotion
hierarchy_candidate_report
sibling_group_candidate_report
layout_energy_report
auto_layout_permission_report
plan_materializer
design_token_report
b_stage_quality_report
dsl_visual_comparison
```

Code evidence:

```text
backend/app/upload_preview/pipeline.py:12-31
backend/app/upload_preview/pipeline.py:63-381
```

## Historical / Compatibility Packages

The following packages remain in `backend/app/` but are not part of current upload-preview runtime:

```text
visual_evidence_normalization
visual_object_candidate_audit
text_aware_visual_object_refinement
text_visual_ownership_gate
symbol_fragment_grouping
```

They still have package APIs and tests:

```text
backend/tests/test_visual_evidence_normalization.py
backend/tests/test_visual_object_candidate_audit.py
backend/tests/test_text_aware_visual_object_refinement.py
backend/tests/test_text_visual_ownership_gate.py
backend/tests/test_symbol_fragment_grouping.py
```

Current docs explicitly classify them as historical public APIs or older M29 audit harnesses.

Code/doc evidence:

```text
docs/engineering/current-mainline-code-map.md:621-718
```

## Removed Runtime Paths

Current docs say these are historical and must not be restored:

```text
M29 Direct compare
legacy M30 materialization product path
M31-M39 / M39.1 runtime
ONNX proposer
old M8-M28 diagnostic endpoints
```

Doc evidence:

```text
AGENTS.md
docs/architecture/api-contracts.md
docs/architecture/backend.md
docs/architecture/overview.md
docs/architecture/observability.md
docs/runbooks/local-setup.md
```

## Environment Variable Debt

`docs/reference/env-vars.md` still lists historical variables:

```text
M30_SHAPE_ERASURE_ENABLED
M30_IMAGE_ERASURE_ENABLED
M30_ACCEPTED_IMAGE_MATERIALIZATION_ENABLED
M30_IMAGE_ASSET_TEXT_ERASURE_ENABLED
M31_UPLOAD_DIAGNOSTICS_ENABLED
M39_CONTENT_CHROME_CLASSIFICATION_ENABLED
M39_ONNX_PROPOSER_ENABLED
M39_1_UNIT_STRUCTURE_READINESS_ENABLED
```

Finding:

```text
These names are historical documentation debt unless still accepted by current settings.
They should not influence current M29 repair design.
```

## Decision Authority

Historical packages must not decide current runtime behavior.

They can be used only as:

```text
historical reference
compatibility API surface
test fixture source
conceptual provenance for old formulas
```

They must not be used to justify:

```text
new upload-preview stage order
new source ownership decision
new cleanup authorization
restoring M30/M31/M39 runtime
```

## Information Loss

### Loss 1: Historical names still shape reasoning

The repository contains many completed plans and old docs for M30/M31/M39. Reading them without current-mainline context makes the architecture look larger than it is.

This is a human-debugging cost, not an immediate runtime bug.

### Loss 2: Old packages preserve useful formulas but stale boundaries

Some historical packages contain useful ideas:

```text
symbol fragment grouping
text/visual ownership routing
visual evidence normalization
candidate audit
```

But their contracts predate the current M29.2/M29.5/promotion boundary. Copying logic from them directly can reintroduce report-as-decision bugs.

### Loss 3: Legacy tests can create false confidence

Passing tests for old audit packages does not prove current upload-preview output quality. Current acceptance must run through the M29 mainline.

## Specialization Risk

Historical packages are more likely to contain old sample-driven thresholds and naming from pre-mainline experiments. They should be audited before reuse.

This does not mean delete immediately. It means do not treat them as active source truth.

## Tests / Guards

Current mainline tests should be preferred for runtime changes:

```text
test_media_internal_decomposition.py
test_transparent_asset_report.py
test_m29_evidence_contract.py
test_internal_source_promotion.py
test_m29_replay_plan.py
test_m29_plan_materializer.py
test_upload_preview_pipeline.py
```

Legacy package tests are compatibility guards only unless a package is reactivated by an explicit plan.

## Findings

### Fact

The active upload-preview pipeline does not import the historical M29.0.x/M29.1 audit packages listed above.

### Fact

The repository still documents these historical packages in the current code map as older harnesses and compatibility exports.

### Inference

They are dead-path debt for current Codia-like quality work unless deliberately migrated into the current source-chain contract.

### Risk

Leaving them in place without a clearer label increases the chance of future fixes being made in the wrong layer or justified by stale contracts.

## Recommended Next Action

Do not delete these packages in the audit phase. Create a later cleanup plan that:

```text
labels them as legacy/compat-only in docs
checks whether any current imports still require them
archives or deletes packages only with tests updated
removes stale env-var documentation if settings no longer accept it
preserves any still-useful formulas by migrating them into current M29.2/M29.6/evidence modules
```
