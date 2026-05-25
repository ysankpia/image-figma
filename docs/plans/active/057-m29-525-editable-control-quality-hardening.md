# 057 M29 525 Editable Control Quality Hardening

- 状态：active
- 创建日期：2026-05-25
- 负责人：Codex

## Goal

Use `/Users/luhui/Downloads/525测试` to improve actual editable reconstruction quality after the 056 stability fixes. The target is not merely that upload-preview completes. The target is that finite UI controls inside the six real samples are split and cleaned in a way that matches source ownership:

```text
finite control background -> draggable shape/image node when evidence supports it
control text -> editable text node when OCR/source ownership supports it
parent raster/copied media -> cleaned only through M29.5 cleanupTargets
cleanup result -> parent background remains, no duplicate text, no dirty foreground block
```

The motivating example is a colored button on a dark background with text. The implementation must generalize to finite controls and must not special-case green, black, literal text, filenames, screenshots, fixed coordinates, or fixed sizes.

## First-Principles Contract

Real goal:

```text
reduce user repair cost in Figma by making obvious finite controls editable while preserving visual correctness
```

Source truth:

```text
source PNG pixels + OCR boxes + raw M29 primitive graph + M29.2 source ownership + M29.3 relations
```

Information-loss points:

```text
1. raw foreground detection can merge button background with parent media
2. M29.2 can leave a finite control as preserve_raster instead of source-owned shape/image
3. M29.5 can replay text/shape but miss cleanup authorization
4. materializer can only consume cleanup; it must not invent ownership or authorization
5. diagnostic render artifacts can mislead inspection if treated as Figma truth
```

Owning layer:

```text
missing control background source -> raw M29 / visual_primitive / M29.2 source ownership
missing internal control source -> M29.6 media internal decomposition / transparent asset report / internal source promotion
missing cleanup authorization -> M29.3 relation graph / M29.5 replay plan / ownership conservation
incorrect cleanup execution -> plan materializer as M29.5 consumer only
```

Do not do:

```text
do not patch Renderer, plugin, or materializer with color/copy/theme/industry/file/path/fixed-bbox rules
do not add DSL schema/API/plugin protocol changes
do not add Pillow/OpenCV/model dependencies
do not optimize one screenshot at the expense of source ownership auditability
```

Next verification:

```text
six-image 525 batch + per-image artifact inspection ledger + targeted regression tests for each owning-layer fix
```

## Scope

Allowed:

- `backend/app/visual_primitive/`
- `backend/app/source_ui_physical_graph/`
- `backend/app/media_internal_decomposition/`
- `backend/app/transparent_asset_report/`
- `backend/app/internal_source_promotion/`
- `backend/app/region_relation_graph/`
- `backend/app/m29_replay_plan/`
- `backend/app/ownership_conservation/`
- `backend/app/plan_materializer/`
- `backend/app/dsl_visual_comparison/` only for diagnostic/report-only inspection support
- focused backend tests for affected layers
- batch validation / inspection scripts when they improve reusable evidence collection
- docs, bug records, and regression matrix updates

Forbidden without migration proposal:

- DSL schema changes
- public API response shape changes
- Renderer or Figma plugin protocol changes
- Figma Auto Layout, Component/Instance, Variant, Vectorization, or variable materialization
- adding runtime dependencies such as Pillow/OpenCV/SAM/ONNX

Forbidden always:

- filename, exact path, sample id, task id, upload order, fixed bbox, fixed coordinate, fixed screen size, literal visible text, brand, industry, theme color, or one-screenshot structure rules
- materializer, Renderer, or plugin patches that invent source owners or cleanup authorization
- cleanup without M29.5 `cleanupTargets`

## Sample Set

```text
/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月23日 17_37_14.png
/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月23日 17_39_56.png
/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月23日 17_48_23.png
/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月23日 17_50_34.png
/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月23日 17_52_19.png
/Users/luhui/Downloads/525测试/微信图片_20260524225318_199_118.png
```

## Stage Loop

1. Run the six-image batch validation.
2. Record the latest ledger path and artifact paths.
3. Inspect each sample using source PNG, `dsl_render.png`, `source_diff.png`, DSL, replay plan, materialization report, M29.6 report, transparent asset report, internal promotion report, and ownership conservation report.
4. Write a per-sample quality ledger with symptoms and owning layer.
5. Pick the highest-impact generic defect.
6. Add focused regression coverage for that owning layer.
7. Implement the smallest general fix.
8. Run targeted pytest.
9. Rerun the six-image batch.
10. Inspect artifacts for degraded or suspicious samples.
11. Update this plan, related bug record, and regression matrix when contract coverage changes.
12. Commit only the stage-scoped files.

## Inspection Ledger Schema

For each sample, record:

```text
sample
taskId
source image
dsl_render
source_diff
dsl_visual_metrics
visible replay count
promoted internal source count
transparent allow/reject counts
controlled structure groups
suspected finite controls
control background source evidence
control text source evidence
cleanupTargets evidence
materializer cleanup result
symptoms
owning layer
next action
```

## Acceptance

- Every new fix is explained by source evidence, relation evidence, M29.5 replay/cleanup authorization, or materializer plan consumption.
- The six 525 samples complete after each substantive fix.
- No ownership conflicts are introduced.
- No report-only surface is treated as actual Figma output.
- No logic is keyed to filenames, paths, literal text, colors, theme, fixed bbox, or one screenshot structure.
- Buttons/finite controls that are accepted by evidence expose editable/draggable foreground without duplicate text or stale foreground residue in copied media.

## Validation

Baseline and finish gate:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/525测试 \
  --poll-timeout 300
```

Core backend regression after substantive fixes:

```bash
cd backend
uv run pytest \
  tests/test_media_internal_decomposition.py \
  tests/test_transparent_asset_report.py \
  tests/test_internal_source_promotion.py \
  tests/test_m29_replay_plan.py \
  tests/test_m29_plan_materializer.py \
  tests/test_upload_preview_pipeline.py \
  tests/test_ownership_conservation.py \
  -q
```

Finish:

```bash
git diff --check
git status --short --branch
```

## Stage Notes

Initial state:

```text
main ahead origin/main by 7 commits
latest stable 525 ledger from 056: backend/tmp/validation/upload_preview_batch_20260525_204625/upload_preview_batch_validation.json
inputCount = 6
completedTaskCount = 6
failedTaskCount = 0
missingArtifactCount = 0
ownershipConflictTypeCounts = {}
totalBStageRepairCost = 35
```

057 begins with a fresh 525 batch and a per-sample artifact inspection ledger before code changes.

Stage 1 finite control background fix:

```text
bug record: docs/bugs/open/011-finite-control-backgrounds-can-be-preserved-as-media.md
implemented without new dependencies
owning layer: raw M29 support scoring + M29.2 source ownership + M29.5 cleanup target pruning + materializer plan consumption
forbidden layer patching avoided: no Renderer/plugin/materializer owner inference
```

Generic formula now used for `unknown / image_like_low_confidence` finite control backgrounds:

```text
finite bbox size/aspect/area ratio
+ high-confidence OCR containment
+ bounded text-area ratio
+ bounded color/texture/edge complexity
+ minimum fill ratio
+ source PNG fill sampling excluding OCR bbox
=> control_background / shape_geometry / shape_replay
```

Validation:

```text
uv run pytest tests/test_ownership_conservation.py tests/test_source_ui_physical_graph.py tests/test_visual_primitive_graph.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py -q
96 passed in 1.96s

uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py tests/test_ownership_conservation.py tests/test_source_ui_physical_graph.py tests/test_visual_primitive_graph.py -q
125 passed in 15.91s

uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/525测试 --poll-timeout 300
ledger: backend/tmp/validation/upload_preview_batch_20260525_222638/upload_preview_batch_validation.json
inputCount = 6
completedTaskCount = 6
failedTaskCount = 0
missingArtifactCount = 0
totalVisibleReplayClaimCount = 370
totalVisibleOwnershipOverlapConflicts = 0
ownershipConflictTypeCounts = {}
```

Tea sample artifact check:

```text
taskId = task_e3bad3f1eefe
source = /Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月23日 17_52_19.png
M29.2 object = m292_object_0108
bbox = [662, 1479, 206, 66]
visualKind = control_background
pixelOwner = shape_geometry
replayDecision = shape_replay
sourceShapeInference = finite_control_low_confidence_unknown
shapeFillOverride = #456441
shapeRadiusOverride = 33
M29.5 action = shape_replay
DSL materialization = independent m29_shape with source_shape_inference style
```

Cleanup note:

```text
The containing bottom media object was later suppressed by visible-overlap suppression,
so no copied image asset exists for that parent media. M29.5 now prunes copied-image
cleanup targets that point at suppressed media and keeps only fallback cleanup for this
shape. This preserves the rule that materializer consumes cleanup authorization only.
```
