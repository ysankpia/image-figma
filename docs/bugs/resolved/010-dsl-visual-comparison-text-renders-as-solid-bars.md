# Bug: DSL visual comparison text renders as solid bars

- 状态：resolved
- 创建日期：2026-05-25
- 影响范围：`backend/app/dsl_visual_comparison/` report-only artifact；不影响 DSL、Renderer、Figma plugin 或实际 Figma 输出。

## Summary

`m29_dsl_visual_comparison/dsl_render.png` rendered text nodes as solid horizontal bars. This made real-sample artifact inspection misleading because text-heavy regions could look like large white or colored blocks even when the final DSL still contained real text content.

## Reproduction

1. Run upload-preview or batch validation for a text-heavy sample.
2. Open `storage/upload_previews/{taskId}/m29_dsl_visual_comparison/dsl_render.png`.
3. Observe that DSL text nodes are represented by solid bars instead of text-like marks.

## Root Cause

The report-only approximate renderer used `fill_rect` for text:

```text
text bbox -> one centered solid horizontal rectangle
```

This was acceptable for early metric smoke tests, but it was too coarse for 525 real-sample visual inspection.

## Fix

Use a dependency-free text-like raster texture for diagnostic rendering. The renderer does not add Pillow or other runtime dependencies, does not identify fonts, and does not change DSL, materialization, Renderer, plugin protocol, or actual Figma output.

## Regression Guard

Added `backend/tests/test_dsl_visual_comparison.py::test_text_rendering_uses_glyph_texture_not_solid_bar`. The guard renders a text node and asserts the diagnostic output contains glyph-like texture rather than a long solid bar.

## Validation Evidence

```bash
cd backend
uv run pytest tests/test_dsl_visual_comparison.py -q
uv run pytest tests/test_dsl_visual_comparison.py tests/test_upload_preview_pipeline.py -q
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/525测试 --poll-timeout 300
```

Results:

```text
tests/test_dsl_visual_comparison.py: 1 passed
dsl visual comparison + upload preview pipeline: 8 passed
525 full batch ledger: backend/tmp/validation/upload_preview_batch_20260525_204625/upload_preview_batch_validation.json
inputCount = 6
completedTaskCount = 6
failedTaskCount = 0
missingArtifactCount = 0
ownershipConflictTypeCounts = {}
totalBStageRepairCost = 35
```

An earlier run at `backend/tmp/validation/upload_preview_batch_20260525_204352/upload_preview_batch_validation.json` failed on sample 6 during OCR with Baidu PP-OCRv5 `SSLEOFError`. A clean full rerun completed afterward, so that failure is recorded as external OCR dependency instability, not this diagnostic renderer change.

## Prevention Notes

Visual comparison artifacts are diagnostic only. They must stay visibly approximate, but they should not introduce large artificial shapes that can be mistaken for actual reconstruction defects.

