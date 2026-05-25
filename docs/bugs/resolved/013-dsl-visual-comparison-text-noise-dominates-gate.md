# Bug: DSL visual comparison text noise dominates gate

- 状态：resolved
- 创建日期：2026-05-26
- 影响范围：`backend/app/dsl_visual_comparison/` report-only metrics 和 `backend/scripts/run_upload_preview_batch_validation.py` ledger summary；不影响 DSL、Renderer、Figma plugin、M29.5 replay plan、materializer output 或 public API。

## Summary

061 主样本集 Stage 2 排查发现，最差样本的 `changedPixelRatio10` 高达 `0.208299`，但 artifact inspection 显示主要红区来自 text bbox：DSL 里的中文内容是正确的，report-only approximate renderer 只是用 dependency-free 伪字形渲染，无法匹配真实字体。

如果继续把全图 `normalizedMeanAbsError` / `changedPixelRatio10` 当唯一 visual gate，会把后续 M29 修复方向带歪：系统会优先追逐字体诊断误差，而不是真实的布局、图片、背景、cleanup、ownership 问题。

## Reproduction

1. Run 061 primary batch:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/测试/images --poll-timeout 300
```

2. Open the Stage 1 ledger:

```text
backend/tmp/validation/upload_preview_batch_20260526_031541/upload_preview_batch_validation.json
```

3. Inspect the worst visual-diff sample:

```text
sample: 39-e588b6e980a0e5b7a5e58e82.png
task: task_f9b3bfc46d7d
changedPixelRatio10: 0.208299
normalizedMeanAbsError: 0.051411
```

4. Compare artifacts:

```text
storage/uploads/task_f9b3bfc46d7d/original.png
storage/upload_previews/task_f9b3bfc46d7d/m29_dsl_visual_comparison/dsl_render.png
storage/upload_previews/task_f9b3bfc46d7d/m29_dsl_visual_comparison/source_diff.png
storage/upload_previews/task_f9b3bfc46d7d/materialized_design/design.dsl.json
```

5. The DSL text content is correct Chinese, for example `生产看板`、`全部产线`、`冲压一线`、`质检汇总`、`设备稼动率`、`班组绩效`。 The diff is dominated by report-only approximate text rendering, not by source ownership loss.

## Root Cause

First-principles source chain:

```text
source PNG pixels
-> final materialized DSL
-> report-only approximate DSL rasterization
-> full-image pixel diff
```

The information-loss point is the report renderer, not M29 source ownership:

```text
Figma/real UI text rasterization cannot be recovered by the dependency-free approximate renderer.
```

The old metric treated every text pixel as equally authoritative evidence for visual failure:

```text
all pixels -> normalizedMeanAbsError / changedPixelRatio10
```

That is wrong for a diagnostic renderer whose text drawing is explicitly approximate. Text regions should still be reported, but they must not dominate the visual regression gate used to decide whether an M29 algorithm change degraded real UI structure.

## Fix

Added a text-excluded gate metric while preserving the original full-image metrics:

```text
visible DSL text bboxes
-> text exclusion mask
-> full diff metrics remain unchanged
-> nonText/gate diff metrics exclude text bbox pixels
```

New report fields:

```text
nonTextPixelComparedCount
nonTextMeanAbsChannelError
nonTextNormalizedMeanAbsError
nonTextChangedPixelRatio10
gateNormalizedMeanAbsError
gateChangedPixelRatio10
gateFallbackReason
textExcludedPixelCount
textExcludedCoverage
```

The batch ledger summary now also records:

```text
averageDslVisualGateNormalizedMeanAbsError
maxDslVisualGateChangedPixelRatio10
```

If visible text bboxes cover every compared pixel, the gate metrics fall back to full-image metrics and record:

```text
gateFallbackReason = no_non_text_pixels
```

This prevents all-text samples from reporting fake-zero structural gate error.

The fix does not add font dependencies, does not identify fonts, does not change real Figma output, and does not hide the original all-pixel diff.

## Regression Guard

Added tests:

```text
backend/tests/test_dsl_visual_comparison.py::test_text_exclusion_mask_tracks_visible_text_bboxes_with_parent_offsets
backend/tests/test_dsl_visual_comparison.py::test_compare_pixels_reports_gate_metrics_excluding_text_regions
backend/tests/test_dsl_visual_comparison.py::test_compare_pixels_falls_back_to_full_metrics_when_text_mask_covers_every_pixel
backend/tests/test_upload_preview_batch_validation_script.py::test_build_summary_separates_unsupported_from_supported_failures
```

Existing test remains:

```text
backend/tests/test_dsl_visual_comparison.py::test_text_rendering_uses_glyph_texture_not_solid_bar
```

## Validation Evidence

Targeted validation:

```bash
python3 -m py_compile backend/app/dsl_visual_comparison/render.py backend/app/dsl_visual_comparison/pipeline.py backend/tests/test_dsl_visual_comparison.py backend/scripts/run_upload_preview_batch_validation.py backend/tests/test_upload_preview_batch_validation_script.py
cd backend && uv run pytest tests/test_dsl_visual_comparison.py tests/test_upload_preview_batch_validation_script.py tests/test_upload_preview_pipeline.py -q
git diff --check
```

Result:

```text
15 passed
```

Primary 061 batch validation:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/测试/images --poll-timeout 300
```

Ledger:

```text
backend/tmp/validation/upload_preview_batch_20260526_040404/upload_preview_batch_validation.json
```

Result:

```text
inputCount: 40
supportedInputCount: 40
completedTaskCount: 40
supportedFailedCount: 0
degradedRecordCount: 0
backendCrashCount: 0
missingArtifactCount: 0
assetFetchFailedCount: 0
averageDslVisualNormalizedMeanAbsError: 0.042053
maxDslVisualChangedPixelRatio10: 0.208299
averageDslVisualGateNormalizedMeanAbsError: 0.004658
maxDslVisualGateChangedPixelRatio10: 0.134558
gateFallbackReason counts: {null: 40}
```

Worst sample after the fix:

```text
sample: 39-e588b6e980a0e5b7a5e58e82.png
task: task_0bc002ab51fa
normalizedMeanAbsError: 0.051411
changedPixelRatio10: 0.208299
textExcludedCoverage: 0.170928
gateNormalizedMeanAbsError: 0.010781
gateChangedPixelRatio10: 0.134558
```

## Prevention Notes

Visual comparison must keep separate meanings:

```text
full diff = useful diagnostic surface, includes approximate text-rendering noise
gate diff = better regression signal for non-text visual structure
```

Do not use text-excluded gate metrics to claim text quality is correct. Text editability and text correctness still require OCR/source ownership/cleanup evidence and, when needed, Figma-visible validation.
