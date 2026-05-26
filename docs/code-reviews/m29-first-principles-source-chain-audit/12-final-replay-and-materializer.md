# 12 Final Replay And Materializer

## Source Truth

Final materialization consumes the promoted M29.2 document and the final M29.5 replay plan.

```text
source PNG
OCR document
raw M29 nodes
promoted M29.2 source objects
final M29.5 replay plan
hierarchy / sibling / layout / auto-layout permission reports
```

Primary package:

```text
backend/app/plan_materializer/
```

Runtime entrypoint:

```text
backend/app/plan_materializer/builder.py:26
```

First-principles role:

```text
Materializer is an executor.
It is not a source owner.
It is not an evidence scorer.
It is not a cleanup authorizer.
```

## Input Artifacts

```text
original PNG
ocr/ocr.json
m29/nodes.json
m29_internal_source_promotion/source_ui_physical_graph.promoted.json
m29_5/replay_plan.json
m29_hierarchy_candidates/hierarchy_candidate_report.json
m29_sibling_groups/sibling_group_candidate_report.json
m29_layout_energy/layout_energy_report.json
m29_auto_layout_permission/auto_layout_permission_report.json
```

Code evidence:

```text
backend/app/upload_preview/pipeline.py:312-331
backend/app/plan_materializer/builder.py:88-108
```

## Output Artifacts

Primary outputs:

```text
materialized_design/design.dsl.json
materialized_design/materialization_report.json
materialized_design/assets/**
```

Report fields include:

```text
summary
options
controlledStructureMaterialization
replayedNodes
skippedItems
warnings
```

Code evidence:

```text
backend/app/plan_materializer/builder.py:144-177
```

## Decision Authority

### This layer can decide

Materializer can decide execution mechanics only:

```text
copy/crop image asset
create DSL node from M29.5 finalReplayAction
sample source-derived text color and shape fill
erase pixels only where M29.5 cleanupTargets allow it
wrap already-replayed visible nodes into transparent controlled groups
record skipped execution reasons
```

### This layer must not decide

Materializer must not decide:

```text
source ownership
visible replay eligibility
candidate confidence
internal media object promotion
transparent asset allow/reject
cleanup authorization
Auto Layout creation
Component/Instance/Variant creation
new visible owner nodes outside M29.5
```

The code matches this boundary. `build_plan_driven_dsl` requires an M29.5 replay plan and raises if it is missing.

Code evidence:

```text
backend/app/plan_materializer/builder.py:90-92
```

## Main Gates

### Replay gate

Every visible node starts from a final M29.5 plan item.

```text
for plan in planItems:
  item = m292_by_id[sourceObjectId]
  action = finalReplayAction
```

Skipped non-visible actions:

```text
preserve_in_parent_raster
suppress_duplicate
fallback_only
diagnostic_only
```

Code evidence:

```text
backend/app/plan_materializer/replay.py:35-45
```

### Supported replay actions

Supported visible actions:

```text
text_replay
image_replay
icon_replay
shape_replay
```

Unsupported action becomes `unsupported_replay_action`, not a guessed node.

Code evidence:

```text
backend/app/plan_materializer/replay.py:54-148
```

### Transparent asset consumption

For promoted internal icons, the materializer may use transparent asset override only if source evidence has:

```text
promotionSource = m29_6_internal_icon_candidate
transparentAssetPath is non-empty
resolved asset file exists
```

If the transparent asset path is absent or missing on disk, materializer falls back to crop mechanics only for an already-approved `icon_replay` source object. It does not promote a candidate.

Code evidence:

```text
backend/app/plan_materializer/replay.py:109-131
backend/app/plan_materializer/replay.py:221-231
```

### Cleanup gate

Copied image cleanup is strictly plan-authorized:

```text
text cleanup requires finalReplayAction == text_replay and copied_image_asset cleanup target
internal icon cleanup requires finalReplayAction == icon_replay and approved reason
shape cleanup requires finalReplayAction == shape_replay and shape_background_contained_by_media
fallback cleanup requires finalReplayAction in visible actions and fallback cleanup target
```

Code evidence:

```text
backend/app/plan_materializer/cleanup.py:185-232
backend/app/plan_materializer/cleanup.py:328-337
```

Internal icon cleanup uses the transparent PNG alpha mask when available.

Code evidence:

```text
backend/app/plan_materializer/cleanup.py:235-260
```

### Controlled structure gate

Controlled structure groups are wrappers around already materialized nodes:

```text
replayed source objects
hierarchy / sibling / layout / auto-layout permission evidence
score >= 0.74
2 <= members <= 16
area ratio <= 0.55
root-level contiguous z-order
```

The group has:

```text
type = group
role = m29_controlled_structure_group
style.fill = None
autoLayoutCreated = False
```

Code evidence:

```text
backend/app/plan_materializer/structure.py:25-80
backend/app/plan_materializer/structure.py:146-168
backend/app/plan_materializer/structure.py:217-277
backend/app/plan_materializer/types.py:7-21
```

## Information Loss

### Loss 1: Missing source object cannot be recovered here

If M29.6 detected an internal icon but transparent/evidence/promotion failed, final M29.2 lacks a source object. Materializer sees nothing to replay.

This explains the common symptom:

```text
text is editable
icon candidate appears in diagnostics
final Figma has no selectable icon
```

The missing step is upstream promotion, not materializer execution.

### Loss 2: Button semantics require visible members first

Controlled structure can group only already replayed nodes. If a button background is still inside a media raster, there is no `m29_shape` member to group with text/icon.

So this layer cannot turn:

```text
raster media + editable text
```

into:

```text
selectable button = background shape + text + icon
```

unless M29.2/M29.5 already produced the visible background/icon source objects.

### Loss 3: Cleanup visual quality is not independently proven

Cleanup fills erased pixels by sampled local background. For text and simple shapes this can be acceptable. For glass/gradient/media backgrounds it can still cause scars. This layer records erase counts, but it does not run a local render-back gate before erasing.

## Known Failure Symptoms

```text
M29.6 candidate exists but no final icon node
promoted internal icon has no transparent asset path
copied media image still contains visual duplicate because cleanup target absent
controlled group rejected because member nodes are not root-contiguous
button/control cannot become a selectable button because its background was never replayed
```

## Tests / Guards

Relevant tests:

```text
backend/tests/test_m29_plan_materializer.py
```

Specific guarded behavior:

```text
promoted internal icon uses M29.5-authorized transparent asset
copied media cleanup requires M29.5 cleanup target
internal asset cleanup requires M29.5 cleanup target
shape cleanup requires M29.5 cleanup target
controlled structure groups only contiguous high-confidence members
controlled structure does not create Auto Layout
```

Code evidence:

```text
backend/tests/test_m29_plan_materializer.py:80-119
backend/tests/test_m29_plan_materializer.py:190-257
backend/tests/test_m29_plan_materializer.py:405-449
backend/tests/test_m29_plan_materializer.py:471-545
```

## Findings

### Fact

Materializer is not the current root cause for missing internal icons. It only replays final M29.5 plan items and only consumes transparent asset override through promoted M29.2 source evidence.

### Fact

Materializer cleanup is correctly permissioned by M29.5 `cleanupTargets`.

### Inference

When a Figma output has editable text but no selectable adjacent icon, the likely break is:

```text
M29.6 candidate
-> transparent asset reject/report-only
-> evidence report_only/reject
-> promotion rejected
-> final M29.5 no icon_replay
-> materializer has no node to create
```

### Risk

Materializer can only group visible nodes that already exist. Codia-like selectable controls need upstream control/background source objects, not downstream grouping hacks.

## Recommended Next Action

Do not patch materializer to infer missing icons or buttons. Fix the bridge before it:

```text
M29.6 candidate execution support
transparent asset preflight
evidence contract allow_visible_replay
internal source promotion
final M29.5 replay/cleanup authorization
```
