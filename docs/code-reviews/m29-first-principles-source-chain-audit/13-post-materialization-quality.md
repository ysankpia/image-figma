# 13 Post-Materialization Quality

## Source Truth

Post-materialization quality reports consume final DSL and M29 reports.

```text
materialized DSL
materialization report
ownership conservation report
hierarchy / sibling / layout / auto-layout reports
design token report
source PNG for visual comparison
```

Primary packages:

```text
backend/app/design_token_report/
backend/app/b_stage_quality_report/
backend/app/dsl_visual_comparison/
```

First-principles role:

```text
These layers measure and summarize final output quality.
They are not source truth.
They do not mutate source ownership, replay plan, assets, or DSL.
```

## Runtime Position

Pipeline order:

```text
materialization
-> design token report
-> B-stage quality report
-> asset publish
-> DSL visual comparison
```

Code evidence:

```text
backend/app/upload_preview/pipeline.py:312-381
```

## Design Token Report

### Source truth

Consumes final DSL plus materialization and M29.5 report metadata.

Code evidence:

```text
backend/app/design_token_report/pipeline.py:18-25
```

### Output

```text
m29_design_tokens/design_token_report.json
```

It extracts:

```text
color tokens
text style tokens
radius tokens
spacing tokens
```

Validation metadata states:

```text
reportOnly = true
dslChanged = false
assetChanged = false
createdVisibleNodeCount = 0
materializationChanged = false
figmaVariablesBound = false
designSystemChanged = false
```

Code evidence:

```text
backend/app/design_token_report/pipeline.py:27-73
```

### Finding

This report can describe token regularity after the fact. It cannot prove a missing icon, button, tab, or marker should exist.

## B-Stage Quality Report

### Source truth

Consumes summary fields from:

```text
ownership
hierarchy
sibling
layout
auto-layout permission
design tokens
materialization
```

Code evidence:

```text
backend/app/b_stage_quality_report/pipeline.py:14-25
backend/app/b_stage_quality_report/quality.py:11-27
```

### Output

```text
m29_b_stage_quality/b_stage_quality_report.json
```

It computes:

```text
quality score
risk summary
repair cost
capability maturity
```

Validation metadata states:

```text
reportOnly = true
dslChanged = false
assetChanged = false
createdVisibleNodeCount = 0
materializationChanged = false
blockingUpload = false
```

Code evidence:

```text
backend/app/b_stage_quality_report/pipeline.py:37-62
```

### Main formulas

Repair cost weights:

```text
ownership_errors: 8
ownership_conflicts: 4
materialization_warnings: 3
materialization_skips: 2
deferred_auto_layout: 1
rejected_auto_layout: 2
token_gaps: 1
```

Quality score:

```text
score = max(0, 1 - min(0.75, totalRepairCost / 400))
```

Code evidence:

```text
backend/app/b_stage_quality_report/quality.py:81-127
```

Capability maturity explicitly classifies:

```text
ownershipConservation = diagnostic-only
hierarchyCandidates = candidate-proposal
siblingGroupCandidates = candidate-proposal
layoutEnergy = candidate-proposal
autoLayoutPermission = permission-only
designTokens = candidate-proposal
bStageQuality = diagnostic-only
```

Code evidence:

```text
backend/app/b_stage_quality_report/quality.py:175-184
```

### Finding

B-stage quality is useful for triage. It is not a blocking acceptance gate and currently cannot prevent a visually wrong materialization from being returned.

## DSL Visual Comparison

### Source truth

Consumes source PNG and final DSL.

Code evidence:

```text
backend/app/dsl_visual_comparison/pipeline.py:12-21
```

### Output

```text
m29_dsl_visual_comparison/dsl_visual_comparison_report.json
m29_dsl_visual_comparison/dsl_render.png
m29_dsl_visual_comparison/source_diff.png
m29_dsl_visual_comparison/source_gate_diff.png
```

It renders an approximate DSL image and computes:

```text
meanAbsChannelError
normalizedMeanAbsError
changedPixelRatio10
nonTextNormalizedMeanAbsError
gateNormalizedMeanAbsError
gateChangedPixelRatio10
```

Text regions are excluded from the gate comparison.

Code evidence:

```text
backend/app/dsl_visual_comparison/pipeline.py:23-75
backend/app/dsl_visual_comparison/pipeline.py:78-151
```

Metadata says:

```text
truthSource = source_png_plus_final_materialized_dsl
approximateRenderer = true
dslChanged = false
assetChanged = false
```

Code evidence:

```text
backend/app/dsl_visual_comparison/pipeline.py:66-72
```

### Finding

Visual comparison is the right direction for render-back validation, but it is currently post-hoc. It does not feed back into M29.5, promotion, cleanup, or materialization decisions.

## Information Loss

### Loss 1: Quality summaries collapse source-chain causes

A high skip count or repair cost does not explain whether the failure happened in:

```text
raw M29
M29.2 ownership
M29.6 candidate extraction
transparent asset preflight
evidence contract
promotion
M29.5 final plan
materializer execution
```

The post-materialization reports need source-chain trace links to become actionable.

### Loss 2: Visual diff cannot identify missing source object ownership

If a button icon is absent but the original media raster still contains it, full-image visual diff can remain acceptable. The user still cannot select/edit the icon.

So visual fidelity alone is not the acceptance function.

Correct acceptance must include:

```text
visual fidelity
selectability/editability
source ownership conservation
cleanup safety
repair cost
```

### Loss 3: Text exclusion hides text-editability regressions

Text exclusion is useful because rendered font differences are expected. But it also means this report cannot judge whether editable text has correct font metrics, baseline, weight, or exact local alignment.

## Known Failure Symptoms

```text
quality score looks medium/high while a user-visible button is not selectable
source diff is acceptable because missing object remains inside fallback/media raster
repair cost identifies skips but not upstream gate reason
B-stage does not block returning a weak DSL
```

## Tests / Guards

Relevant tests:

```text
backend/tests/test_design_token_report.py
backend/tests/test_b_stage_quality_report.py
backend/tests/test_dsl_visual_comparison.py
```

## Findings

### Fact

These modules are correctly report-only today.

### Fact

They are downstream of materialization and cannot create source objects or final replay plan items.

### Inference

They should become verification gates or diagnosis enrichers only after the source-chain contracts are stable. Using them to patch output would repeat the wrong-layer problem.

### Risk

Without source-chain trace aggregation, B-stage quality can understate user repair cost when the output is visually faithful but structurally uneditable.

## Recommended Next Action

Keep these layers report-only for now. Add later:

```text
source-chain failure aggregation
local render-back gate for risky cleanup
editability/selectability metrics independent from visual diff
```

Do not use visual diff as source ownership truth.
