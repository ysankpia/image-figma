# 056 M29 525 Real Sample Batch Hardening

## Status

superseded

This pre-model internal-asset hardening plan is archived as historical context. The active runtime direction was superseded by the completed model-first mainline refactor in `docs/plans/completed/068-m29-model-first-mainline-destructive-refactor.md` and the later replay/asset contract hardening in `docs/plans/completed/069-m29-replay-overlap-and-model-asset-contract-hardening.md`.

## Objective

Use the six-image real sample set in `/Users/luhui/Downloads/525测试` to calibrate and repair the M29 internal asset chain after plans 054 and 055. The goal is not to make one screenshot look better. The goal is to find general evidence-chain defects, fix them at the owning layer, and keep every accepted repair auditable through M29 source ownership, relation evidence, replay plan authorization, and materializer consumption.

## Sample Set

```text
/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月23日 17_37_14.png
/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月23日 17_39_56.png
/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月23日 17_48_23.png
/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月23日 17_50_34.png
/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月23日 17_52_19.png
/Users/luhui/Downloads/525测试/微信图片_20260524225318_199_118.png
```

Single images may be used for diagnosis. Final acceptance for a repair requires the full six-image batch unless a narrower regression test proves the exact invariant and the batch is blocked by infrastructure.

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
- focused backend tests for the affected layer
- batch validation script and ledger improvements
- this plan and related bug/regression docs

Forbidden without a migration proposal:

- DSL schema changes
- public API response shape changes
- Renderer or Figma plugin protocol changes
- Figma Auto Layout, Component/Instance, Variant, Vectorization, or variable materialization
- restoring removed M29 Direct, legacy M30, M31-M39, ONNX proposer, or old product paths

Forbidden always:

- filename, exact path, sample id, task id, upload order, fixed bbox, fixed coordinate, fixed screen size, literal visible text, brand, industry, theme color, or one-screenshot structure rules
- materializer, Renderer, or plugin patches that invent source owners or cleanup authorization
- cleanup without M29.5 `cleanupTargets`

## Owning Layer Policy

Use the artifact trail to choose the owner:

```text
missing or wrong visible source object
-> raw M29 / visual primitive / M29.2 source ownership

wrong containment, overlap, duplicate, or cleanup relation
-> M29.3 relation graph / M29.5 replay plan / ownership conservation

internal media icon, marker, circular dot, table cell foreground, or small UI asset missing
-> M29.6 media internal decomposition / transparent asset report / internal source promotion

dirty transparent cutout or background block
-> transparent asset alpha mask / edge-alpha gate / copied media alpha-mask cleanup

authorized plan item materializes incorrectly
-> plan materializer, but only as a consumer of M29.5 plan and asset evidence
```

If the owning layer is unclear, stop the repair loop and run a first-principles gate:

```text
real goal
source truth
information-loss point
owning layer
do-not-do
next verification
```

## Baseline Command

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/525测试 \
  --poll-timeout 300
```

The script writes a validation ledger under:

```text
backend/tmp/validation/upload_preview_batch_<timestamp>/
```

Each task must expose the artifacts needed for diagnosis:

```text
stage_timings.json
materialized_design/design.dsl.json
materialized_design/materialization_report.json
m29_media_internal_decomposition/media_internal_decomposition_report.json
m29_transparent_assets/transparent_asset_report.json
m29_internal_source_promotion/internal_source_promotion_report.json
m29_5/replay_plan.json
m29_dsl_visual_comparison/dsl_visual_comparison_report.json
m29_dsl_visual_comparison/dsl_render.png
m29_dsl_visual_comparison/source_diff.png
```

## Stage Loop

For each repair stage:

```text
1. Reproduce or identify a batch artifact failure.
2. Assign owning layer from reports, images, DSL, and materialization report.
3. Implement the smallest general fix at that layer.
4. Add or update a focused regression test.
5. Run targeted pytest for the affected layer.
6. Run the six-image batch validation.
7. Inspect artifacts for every degraded or suspicious sample.
8. Update this plan, bug 009, or regression matrix when the contract changes.
9. Commit only the stage-scoped files.
```

## Initial Suspect Classes

These are diagnosis buckets, not special cases:

- UI labels/buttons inside colored or dark finite backgrounds should be owned by source evidence and cleaned only through M29.5 authorization.
- `preserve_raster` media can retain the complex background while internal UI foreground becomes promoted source evidence only after M29.6, transparent asset, and M29.5 gates.
- Circular markers, table dots, tiny internal icons, separators, and local visual marks need generic pixel/component/repetition evidence, not OCR-only anchors.
- Transparent PNGs must not carry visible background blocks; edge alpha and foreground cohesion gates should reject dirty cutouts.
- Parent copied media cleanup must erase only the M29.5-authorized promoted internal asset pixels and must not damage unrelated raster background.

## Validation Set

Core regression after each substantive backend fix:

```bash
cd backend
uv run pytest \
  tests/test_media_internal_decomposition.py \
  tests/test_transparent_asset_report.py \
  tests/test_internal_source_promotion.py \
  tests/test_m29_replay_plan.py \
  tests/test_m29_plan_materializer.py \
  tests/test_upload_preview_pipeline.py \
  -q
```

Finish-gate validation:

```bash
git diff --check
git status --short --branch
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/525测试 \
  --poll-timeout 300
```

## Stage Notes

- Baseline ledger:

```text
backend/tmp/validation/upload_preview_batch_20260525_195912/upload_preview_batch_validation.json
```

Baseline result:

```text
inputCount = 6
completedTaskCount = 6
failedTaskCount = 0
missingArtifactCount = 0
ownershipConflictTypeCounts = {"invalid_copied_image_asset_cleanup": 12}
totalBStageRepairCost = 547
totalPromotedInternalSourceObjectCount = 13
averageDslVisualNormalizedMeanAbsError = 0.016526
maxDslVisualChangedPixelRatio10 = 0.080846
```

First repair stage:

```text
owner = ownership_conservation
problem = M29.5 and materializer already support promoted internal icon copied-image cleanup, but ownership conservation still treated copied-image cleanup as valid only for text_replay plan items.
fix = allow copied-image cleanup claims for icon_replay only when the plan item is a promoted M29.6 internal icon, sourceEvidence links it to the parent media, transparentAssetPath exists, cleanup reason is promoted_internal_asset_contained_by_media, and M29.3 relation proves containment/near-equal.
guard = plain unpromoted icon copied-image cleanup remains invalid.
```

Validation:

```bash
cd backend
uv run pytest tests/test_ownership_conservation.py -q
uv run pytest tests/test_ownership_conservation.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/525测试 --poll-timeout 300
```

Validation results:

```text
tests/test_ownership_conservation.py: 14 passed
ownership/replay/materializer/upload pipeline focused regression: 52 passed
post-fix ledger: backend/tmp/validation/upload_preview_batch_20260525_200800/upload_preview_batch_validation.json
inputCount = 6
completedTaskCount = 6
failedTaskCount = 0
missingArtifactCount = 0
ownershipConflictTypeCounts = {}
totalBStageRepairCost = 403
averageDslVisualNormalizedMeanAbsError = 0.016526
maxDslVisualChangedPixelRatio10 = 0.080846
```

Infrastructure note:

```text
An intermediate rerun at backend/tmp/validation/upload_preview_batch_20260525_200553 failed on sample 3 during OCR with Baidu PP-OCRv5 HTTPS SSLEOFError. A clean full rerun completed afterward, so this is recorded as external OCR dependency instability, not an M29 regression.
```

Second repair stage:

```text
owner = b_stage_quality_report
problem = B-stage repair cost treated every materialization skip as actionable. In real sample 6, 98 skipped items were intentional non-visible actions (`diagnostic_only`, `suppress_duplicate`, `preserve_in_parent_raster`), so the report produced a low grade despite low visual diff and zero ownership conflicts.
fix = keep total/non-actionable skipped counts for audit, but count only actionable skipped reasons toward materialization repair cost.
guard = actionable skipped reasons such as `missing_text` still add repair cost.
```

Validation:

```bash
cd backend
uv run pytest tests/test_b_stage_quality_report.py -q
uv run pytest tests/test_b_stage_quality_report.py tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py -q
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/525测试 --poll-timeout 300
```

Validation results:

```text
tests/test_b_stage_quality_report.py: 7 passed
b-stage/upload/replay/materializer/ownership focused regression: 59 passed
post-calibration ledger: backend/tmp/validation/upload_preview_batch_20260525_202200/upload_preview_batch_validation.json
inputCount = 6
completedTaskCount = 6
failedTaskCount = 0
missingArtifactCount = 0
ownershipConflictTypeCounts = {}
totalBStageRepairCost = 35
averageDslVisualNormalizedMeanAbsError = 0.016526
maxDslVisualChangedPixelRatio10 = 0.080846
quality grades = high for all six records
```

Third repair stage:

```text
owner = dsl_visual_comparison
problem = report-only DSL visual comparison rendered every text node as one solid horizontal bar. This made `dsl_render.png` and `source_diff.png` misleading during 525 artifact inspection because diagnostic artifacts could look like large white/color blocks even when DSL text content was present.
fix = replace the solid bar with a dependency-free text-like glyph texture based on the DSL text content and bbox. This does not add Pillow, does not identify fonts, and does not change DSL, materialization, Renderer, plugin protocol, or actual Figma output.
guard = focused renderer test asserts text diagnostics contain glyph-like texture and not a long solid bar.
```

Validation:

```bash
cd backend
uv run pytest tests/test_dsl_visual_comparison.py -q
uv run pytest tests/test_dsl_visual_comparison.py tests/test_upload_preview_pipeline.py -q
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/525测试 --poll-timeout 300
```

Validation results:

```text
tests/test_dsl_visual_comparison.py: 1 passed
dsl visual comparison + upload preview pipeline: 8 passed
post-fix ledger: backend/tmp/validation/upload_preview_batch_20260525_204625/upload_preview_batch_validation.json
inputCount = 6
completedTaskCount = 6
failedTaskCount = 0
missingArtifactCount = 0
ownershipConflictTypeCounts = {}
totalBStageRepairCost = 35
averageDslVisualNormalizedMeanAbsError = 0.018365
maxDslVisualChangedPixelRatio10 = 0.084364
```

Infrastructure note:

```text
An intermediate rerun at backend/tmp/validation/upload_preview_batch_20260525_204352 failed on sample 6 during OCR with Baidu PP-OCRv5 HTTPS SSLEOFError. A clean full rerun completed afterward, so this is recorded as external OCR dependency instability, not a DSL visual comparison regression.
```
