# 06 M29.5 Replay Plan

## Source Truth

M29.5 consumes:

```text
M29.2 source ownership document
M29.3 relation graph report
M29.4 weak structural cluster report
```

Primary package:

```text
backend/app/m29_replay_plan/
```

Runtime entrypoint:

```text
backend/app/m29_replay_plan/pipeline.py:20
```

First-principles role:

```text
M29.5 is the formal permission layer before materialization.
It decides finalReplayAction, targetRole, visible-node order, duplicate suppression, node budget suppression, and cleanupTargets.
It does not create DSL nodes itself.
```

This layer is one of the most important architecture boundaries in the current system.

## Input Artifacts

```text
m29_2/source_ui_physical_graph.json
m29_3/region_relation_graph_report.json
m29_4/stable_design_cluster_report.json
```

Inputs are normalized in:

```text
backend/app/m29_replay_plan/normalization.py
backend/app/m29_replay_plan/lookups.py
```

## Output Artifacts

Primary output:

```text
m29_5/replay_plan.json
```

Each `planItem` contains:

```text
id
sourceObjectId
bbox
finalReplayAction
targetRole
pixelOwner
cleanupTargets
suppressedSourceObjectIds
relationEdgeIds
clusterIds
confidence
sourceEvidence
reasons
risks
```

Code evidence:

```text
backend/app/m29_replay_plan/pipeline.py:58-73
```

Validation enforces that M29.5 is still not a DSL writer:

```text
backend/app/m29_replay_plan/validation.py:6-17
```

## Decision Authority

### This layer can decide

M29.5 can decide:

```text
finalReplayAction:
  text_replay
  image_replay
  icon_replay
  shape_replay
  preserve_in_parent_raster
  suppress_duplicate
  fallback_only
  diagnostic_only

targetRole:
  m29_text
  m29_image
  m29_symbol
  m29_shape

visible replay order
near-equal duplicate suppression
visible overlap duplicate suppression
node budget suppression
fallback cleanup target
copied_image_asset cleanup target
```

### This layer must not decide

M29.5 must not decide:

```text
raw source detection
OCR correctness
M29.2 source ownership
transparent asset alpha generation
evidence contract allow/reject
promotion
actual pixel erasure
actual DSL node construction
Renderer/Figma behavior
```

Materializer must consume this plan; it must not recreate these permissions downstream.

## Main Formulas And Gates

### Replay action mapping

M29.5 maps M29.2 owner/decision/confidence to final action:

```text
text_replay + editable_text + confidence != low -> text_replay
image_replay + preserve_raster + confidence != low -> image_replay
icon_replay + raster_icon + confidence != low -> icon_replay
shape_replay + shape_geometry + confidence != low -> shape_replay
preserve_in_parent_raster -> preserve_in_parent_raster
fallback_only owner -> fallback_only
else -> diagnostic_only
```

Code evidence:

```text
backend/app/m29_replay_plan/decisions.py:8-24
```

This is the correct place for final visible replay eligibility, but it relies completely on M29.2/promotion getting source ownership right.

### Target role

Mapping:

```text
text_replay -> m29_text
image_replay -> m29_image
icon_replay -> m29_symbol
shape_replay -> m29_shape
```

Code evidence:

```text
backend/app/m29_replay_plan/decisions.py:27-33
```

There is no current target role for:

```text
button
tab_item
selected_marker
table_marker
action_item_group
```

That is intentional for now. It explains why the current output can be visually better but still not Codia-like in structure.

### Cleanup target generation

Every visible replay gets fallback cleanup:

```text
{"target": "fallback", "reason": "replayed_visible_object"}
```

Code evidence:

```text
backend/app/m29_replay_plan/cleanup.py:6-12
```

Text inside media gets copied image cleanup:

```text
text_replay
+ relation to preserve_raster image
+ contained_by / contains / near_equal / sufficient overlap
=> copied_image_asset cleanup target
```

Code evidence:

```text
backend/app/m29_replay_plan/cleanup.py:19-37
backend/app/m29_replay_plan/cleanup.py:135-145
```

Shape inside media gets copied image cleanup with stricter overlap:

```text
shape_replay
+ contained in preserve_raster image
=> copied_image_asset cleanup target
```

Code evidence:

```text
backend/app/m29_replay_plan/cleanup.py:40-60
backend/app/m29_replay_plan/cleanup.py:161-173
```

Promoted internal icons get copied image cleanup only when source evidence proves the promotion parent:

```text
promotionSource == m29_6_internal_icon_candidate
+ mediaSourceObjectId exists
+ media source object is image_replay / preserve_raster
+ M29.3 relation proves containment or sufficient overlap
=> copied_image_asset cleanup target
```

Code evidence:

```text
backend/app/m29_replay_plan/cleanup.py:63-87
backend/app/m29_replay_plan/cleanup.py:148-158
```

Label-anchored blocked assets have a parallel cleanup path:

```text
labelAnchorOcrBoxId
+ blockedIds
+ contained in media
=> copied_image_asset cleanup target
```

Code evidence:

```text
backend/app/m29_replay_plan/cleanup.py:89-113
```

This is the critical contract:

```text
cleanup is not a materializer guess.
cleanup is a plan item permission.
```

### Near-equal duplicate suppression

M29.5 suppresses near-equal source objects using M29.3 edges:

```text
primarySetRelation == near_equal
then suppress lower priority object
```

Priority:

```text
editable_text: 50
preserve_raster: 40
raster_icon: 35
shape_geometry: 30
fallback_only: 10
diagnostic_only: 0
confidence breaks ties
```

Code evidence:

```text
backend/app/m29_replay_plan/decisions.py:36-77
```

Promoted internal icons are special-cased to keep the higher evidence score:

```text
both promotionSource == m29_6_internal_icon_candidate
=> compare evidenceScore
```

Code evidence:

```text
backend/app/m29_replay_plan/decisions.py:52-60
backend/app/m29_replay_plan/decisions.py:80-102
```

This is reasonable, but it creates a dependency on promotion writing honest `evidenceScore`.

### Visible overlap suppression

M29.5 suppresses visible overlap duplicates after initial action mapping:

```text
same visible action + high containment -> suppress duplicate
image over icon -> image can suppress icon unless icon is proven promoted/anchored over parent media
text over icon -> text can suppress icon unless promoted icon has low textOverlapRatio
```

Code evidence:

```text
backend/app/m29_replay_plan/overlap.py:9-39
backend/app/m29_replay_plan/overlap.py:51-87
```

Promoted internal icon over parent media is explicitly preserved:

```text
promotionSource == m29_6_internal_icon_candidate
+ mediaSourceObjectId == media source id
+ transparentAssetPath exists
=> do not suppress icon under image
```

Code evidence:

```text
backend/app/m29_replay_plan/overlap.py:77-82
backend/app/m29_replay_plan/overlap.py:90-117
```

Label-overlap exemption:

```text
promoted internal icon + textOverlapRatio <= 0.14
=> do not suppress icon under text overlap
```

Code evidence:

```text
backend/app/m29_replay_plan/overlap.py:42
backend/app/m29_replay_plan/overlap.py:83-104
```

This is a useful repair for OCR bbox overlap, but it is also a threshold that belongs in the heuristic ledger.

### Node budget

Visible items are capped:

```text
max_visible_nodes = 260
```

Sort order:

```text
shape_replay
image_replay
icon_replay
text_replay
confidence
sourceObjectId
```

Items past the cap become `suppress_duplicate / node_budget_suppressed`.

Code evidence:

```text
backend/app/m29_replay_plan/types.py:21-26
backend/app/m29_replay_plan/budget.py:8-26
```

## Information Loss

### Loss 1: No source object means no plan item

M29.5 can only plan for M29.2 source objects. Missing button backgrounds, icons, selected markers, or table markers cannot appear here.

### Loss 2: Target roles are primitive, not control-level

M29.5 only targets:

```text
m29_text
m29_image
m29_symbol
m29_shape
```

So even when a button is visually represented by shape + icon + text, M29.5 does not emit a first-class button/action-item plan. Later hierarchy/sibling/layout reports may wrap structure, but C-stage materialization currently remains controlled.

### Loss 3: Cleanup depends on relation edges and source evidence

For promoted internal icons, cleanup target requires:

```text
promotionSource
mediaSourceObjectId
transparentAssetPath
M29.3 containment/overlap edge
```

If any part is missing, the icon may replay without copied asset cleanup, or not replay at all depending on earlier gates.

### Loss 4: Special exemptions depend on promotion provenance

Overlap suppression exemptions for promoted icons are good, but they are also proof that M29.5 is now consuming promotion-specific sourceEvidence. That makes the promotion contract critical.

## Known Failure Symptoms Mapped To This Layer

### Text selectable but icon not selectable

If promotion never created a source object:

```text
M29.5 cannot plan icon_replay.
```

If promotion created the object but sourceEvidence is incomplete:

```text
M29.5 may suppress it under parent media/text,
or may refuse copied image cleanup.
```

### Button can be seen but not dragged as a button

M29.5 has no `button_replay` or `control_replay` action. It can replay primitive shape/text/icon/image items, not a semantic button. A button-like draggable group would need controlled structure grouping after primitive replay, not materializer invention.

### Background residual/double shadow

Owning chain:

```text
M29.5 cleanupTargets missing or wrong
-> materializer cannot legally erase copied media/fallback pixels
```

If cleanupTargets are correct but artifact is wrong, owner moves to plan materializer cleanup execution.

## Tests / Guards

Direct tests:

```text
backend/tests/test_m29_replay_plan.py
```

Important guards:

```text
test_m295_maps_m292_replay_decisions_to_plan_actions
test_m295_plan_items_are_sorted_for_replay_layer_order
test_m295_preserve_raster_text_has_no_cleanup_targets
test_m295_editable_text_inside_media_declares_fallback_and_asset_cleanup
test_m295_shape_inside_media_declares_copied_asset_cleanup
test_m295_keeps_promoted_internal_icon_over_parent_media
test_m295_keeps_higher_evidence_promoted_internal_icon_for_near_equal_candidates
test_m295_keeps_promoted_internal_icon_with_low_label_bbox_overlap
test_m295_keeps_label_anchored_blocked_icon_over_parent_media
test_m295_does_not_add_copied_cleanup_for_unpromoted_icon
test_m295_records_cluster_support_without_semantic_role_promotion
test_m295_node_budget_suppresses_low_priority_visible_items
```

Contract matrix:

```text
M29-CR-026..034 and promoted-internal cleanup rows
```

## Findings

### P1: M29.5 is the correct cleanup authority, and current code mostly respects it

Evidence:

```text
backend/app/m29_replay_plan/cleanup.py:6-37
backend/app/m29_replay_plan/cleanup.py:63-87
backend/app/plan_materializer/cleanup.py consumes cleanupTargets downstream
```

Judgment:

```text
This is the right architecture. Cleanup must stay plan-authorized.
```

Recommended next action:

```text
When auditing materializer, verify it does not add cleanup beyond M29.5 targets.
```

### P1: M29.5 cannot solve missing internal control/background objects

Evidence:

```text
backend/app/m29_replay_plan/pipeline.py:32-57
```

Judgment:

```text
M29.5 only maps existing source objects. If Google button background or bottom marker never reaches promoted M29.2, M29.5 cannot produce it.
```

Recommended next action:

```text
Audit M29.6/evidence/promotion for non-icon internal UI elements, especially control backgrounds and selected markers.
```

### P2: Promoted internal icon replay depends on sourceEvidence shape

Evidence:

```text
backend/app/m29_replay_plan/cleanup.py:63-87
backend/app/m29_replay_plan/overlap.py:90-117
backend/app/m29_replay_plan/decisions.py:80-102
```

Judgment:

```text
This is an acceptable cross-stage contract, but it must be explicitly documented and tested. If promotion omits transparentAssetPath, mediaSourceObjectId, evidenceScore, or textOverlapRatio, M29.5 behavior changes.
```

Recommended next action:

```text
Audit internal_source_promotion contract and evidence source fields.
```

### P2: Overlap suppression has necessary but heuristic promoted-icon exemptions

Evidence:

```text
backend/app/m29_replay_plan/overlap.py:42
backend/app/m29_replay_plan/overlap.py:83-104
```

Judgment:

```text
The threshold is not sample-specific, but it is a hidden product-quality gate. It should be tracked in the heuristic ledger with real samples where OCR bbox overlaps icons.
```

Recommended next action:

```text
Add `MAX_PROMOTED_INTERNAL_ICON_TEXT_OVERLAP_RATIO = 0.14` to the specialization/heuristic ledger.
```

### P2: M29.4 cluster support is recorded but deliberately non-semantic

Evidence:

```text
backend/app/m29_replay_plan/report.py:20-21
backend/tests/test_m29_replay_plan.py::test_m295_records_cluster_support_without_semantic_role_promotion
```

Judgment:

```text
This prevents fake SearchBar/Card/Button components. But it also means current output will remain primitive-layer, not fully Codia-like, until controlled grouping gets a separate contract.
```

Recommended next action:

```text
Roadmap should separate "primitive selectable fidelity" from "semantic/grouped control fidelity".
```

## Recommended Next Action

Continue to ownership conservation:

```text
Check whether ownership conflicts are actually catching double-owned pixels and whether it only reports risks or affects materialization.
```
