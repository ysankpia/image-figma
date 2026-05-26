# 04 M29.3 Region Relation

## Source Truth

M29.3 consumes the M29.2 source object list and computes pairwise bbox relations.

Primary code:

```text
backend/app/region_relation_kernel.py
backend/app/region_relation_graph_report.py
```

Runtime entrypoint:

```text
backend/app/region_relation_graph_report.py:18
```

First-principles role:

```text
M29.3 does not discover new objects.
M29.3 does not decide source ownership.
M29.3 only preserves geometry relations between objects that M29.2 already admitted.
```

This means M29.3 cannot fix a missing icon, missing button background, missing table marker, or missing selected-state marker. It can only help downstream prove relations among existing source objects.

## Input Artifacts

```text
m29_2/source_ui_physical_graph.json
```

The report normalizes `sourceObjects` into relation nodes:

```text
id
bbox
pixelOwner
replayDecision
confidence
visualKind
```

Code evidence:

```text
backend/app/region_relation_graph_report.py:25-27
backend/app/region_relation_graph_report.py:63-90
```

## Output Artifacts

Primary output:

```text
m29_3/region_relation_graph_report.json
```

Fields:

```text
nodes
edges
skippedItems
summary.primarySetRelationCounts
summary.secondaryGeometryRelationCounts
meta.dslChanged = false
meta.assetChanged = false
meta.createdVisibleNodeCount = 0
```

Code evidence:

```text
backend/app/region_relation_graph_report.py:29-60
```

## Decision Authority

### This layer can decide

M29.3 can decide:

```text
primarySetRelation:
  near_equal
  contains
  contained_by
  overlaps
  disjoint

secondaryGeometryRelations:
  near
  left_of / right_of
  above / below
  aligned_left / aligned_center_x / aligned_right
  aligned_top / aligned_center_y / aligned_bottom
  same_width / same_height / same_size

relation metrics:
  intersection area
  containment ratios
  gap distance
  near/alignment thresholds
```

### This layer must not decide

M29.3 must not decide:

```text
visible replay
cleanup target
asset replacement
source promotion
button/control grouping
Auto Layout
component creation
fallback erasure
```

Validation enforces report-only behavior:

```text
backend/app/region_relation_graph_report.py:144-155
```

## Main Formulas And Gates

### Primary relation

For two bboxes:

```text
intersection = area(left ∩ right)
left_in_right = intersection / area(left)
right_in_left = intersection / area(right)
```

Decision:

```text
if left_in_right >= 0.90 and right_in_left >= 0.90:
  near_equal
elif right_in_left >= 0.95:
  contains
elif left_in_right >= 0.95:
  contained_by
elif intersection > 0:
  overlaps
else:
  disjoint
```

Code evidence:

```text
backend/app/region_relation_kernel.py:63-74
backend/app/region_relation_kernel.py:106-121
```

This is clean, primitive geometry. It does not depend on UI text, brand, color, task id, or sample path.

### Near threshold

Near threshold uses the shorter dimension, with a floor for thin objects:

```text
left_short = max(min(width, height), thin_min_dimension_px)
right_short = max(min(width, height), thin_min_dimension_px)
scaled = near_scale * min(left_short, right_short)
nearThreshold = clamp(scaled, near_base_px, near_max_px)
```

Code evidence:

```text
backend/app/region_relation_kernel.py:168-172
```

This is important for separators and selected indicators. It avoids a 1-2 px line producing a zero-near radius, but caps the attraction radius.

### Alignment threshold

Alignment threshold scales with the larger bbox dimension, capped:

```text
scaled = alignment_scale * min(max(left_w,left_h), max(right_w,right_h))
alignmentThreshold = clamp(scaled, alignment_base_px, alignment_max_px)
```

Code evidence:

```text
backend/app/region_relation_kernel.py:175-177
```

This supports row/column reasoning without hardcoded screen coordinates.

### Secondary relation

The secondary relation is purely geometric:

```text
gap <= nearThreshold -> near
x2(left) <= x(right) -> left_of
x2(right) <= x(left) -> right_of
y2(left) <= y(right) -> above
y2(right) <= y(left) -> below
center/edge deltas <= alignmentThreshold -> aligned_*
similar width/height -> same_*
```

Code evidence:

```text
backend/app/region_relation_kernel.py:124-165
```

## Information Loss

### Loss 1: M29.3 discards deep source evidence

M29.3 nodes keep only:

```text
id, bbox, pixelOwner, replayDecision, confidence, visualKind
```

It does not keep:

```text
ocr ids
raw M29 ids
blocked ids
transparent asset path
promotion source
evidence score
text anchor evidence
cleanup risk
```

Code evidence:

```text
backend/app/region_relation_graph_report.py:80-89
```

This is acceptable for a geometry graph, but downstream that needs source provenance must read from M29.2/M29.5 sourceEvidence, not from M29.3.

### Loss 2: Relations are pairwise, not structured proof

M29.3 outputs all pairwise edges. It does not answer:

```text
is this a button?
is this a tab item?
is this an action row?
is this an icon-text pair?
is this a selected-state marker?
```

Those require hypothesis/evidence layers above M29.3.

### Loss 3: Missing source objects remain missing

If M29.2 has no source object for a Google icon or button background, M29.3 cannot represent relations to it.

This is a hard source-chain rule:

```text
no source object -> no relation node -> no M29.4 cluster -> no M29.5 plan item
```

## Known Failure Symptoms Mapped To This Layer

### Text exists but icon/button is missing

If only the text source object exists:

```text
M29.3 can relate text to media,
but cannot relate text to a missing icon/control background.
```

The owner is upstream source generation or promotion, not M29.3.

### Cleanup authorization is wrong

M29.5 uses M29.3 relation edges to decide copied image cleanup containment. If M29.3 relation is wrong, cleanup can be wrong. But if M29.3 relation is correct and cleanup still wrong, the owner is M29.5 cleanup policy or materializer consumption.

## Tests / Guards

Direct tests:

```text
backend/tests/test_region_relation_kernel.py
backend/tests/test_region_relation_graph_report.py
```

Important coverage:

```text
near_equal_for_almost_same_ocr_and_m29_bbox
left_contains_right_when_right_is_mostly_inside_left
close_row_text_and_icon_have_near_left_and_center_alignment
thin_separator_six_pixels_away_is_still_near
test_m2931_empty_and_single_graphs_are_report_only
test_m2931_primary_relation_counts_cover_core_set_relations
test_m2931_secondary_relations_preserve_direction_alignment_and_size
```

Contract matrix:

```text
docs/engineering/m29-contract-regression-matrix.md
M29-CR-017..021
```

## Findings

### P2: M29.3 is clean geometry, but insufficient as a control proof

Evidence:

```text
backend/app/region_relation_kernel.py:54-91
backend/app/region_relation_graph_report.py:93-110
```

Judgment:

```text
The bbox relation kernel is good. The wrong abstraction would be pretending pairwise bbox edges are enough to prove a button, tab item, action row, or Codia-like structure.
```

Recommended next action:

```text
Use M29.3 as relation evidence only. Higher layers need explicit evidence contracts for icon-text-control hypotheses.
```

### P2: M29.3 drops provenance needed by later risk gates

Evidence:

```text
backend/app/region_relation_graph_report.py:80-89
```

Judgment:

```text
This is fine for a geometry report. But downstream should not try to infer promotion/transparent/anchor facts from M29.3.
```

Recommended next action:

```text
When auditing M29.5 and evidence contract, verify they read provenance from M29.2/M29.6/transparent/evidence reports, not from relation edges alone.
```

### P3: Pre-promotion vs post-promotion relation reports are not preserved under separate final artifact names

Evidence:

```text
upload_preview/pipeline.py rebuilds M29.3 after promotion and writes to the same m29_3 output path.
```

Judgment:

```text
Runtime is correct because final relation graph should use promoted M29.2. Debugging is weaker because default artifacts lose the pre-promotion graph unless separately captured.
```

Recommended next action:

```text
Consider future evidence artifact retention, not runtime logic changes.
```

## Recommended Next Action

Continue to M29.4:

```text
Verify whether weak structural clusters are truly report-only and whether they provide enough signal for repeated rows/action groups without becoming fake components.
```
