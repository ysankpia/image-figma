# Bug: Composite media outer shell duplicates top tab text

- 状态：resolved
- 创建日期：2026-05-21
- 影响范围：M30.7 composite media materialization in the M30 upload preview pipeline

## Summary

After M30.7, the top tab row around `推荐 / 穿搭 / 美妆 / 旅行 / 探店 / 家居 / 美食` could appear doubled in Figma. The carousel itself was draggable, but M30 also materialized a larger composite media shell that included the tab row above the carousel.

## Reproduction

1. Upload the current sample PNG through `/api/upload-m30-preview`.
2. Inspect task `task_0f4b0395f436`.
3. `m30/m30_materialized_dsl.json` contained two composite media nodes:
   - `refined_0018` at `[18,236,817,241]`
   - `refined_0028` at `[18,173,817,304]`
4. `refined_0028.png` visibly contained the tab row and the carousel. The tab labels were also emitted as editable `m30_text_member` nodes, so the same text pixels rendered twice.

## Root Cause

M30.7 accepted every large `decision=partially_separated` object with `combinedAssetPath`. That was too broad. M29.0.5 may emit nested composite candidates for the same physical media block: a tight carousel candidate and a larger outer shell that also includes UI chrome. M30.7 had no claim rule for nested composite media bboxes, so both rasters were materialized.

The first-principles failure was pixel ownership: editable top-tab text owned the foreground text pixels, while the larger lower raster still owned the same baked text pixels.

## Fix

`append_composite_media_nodes` now collects valid composite candidates first, sorts them by bbox area from small to large, and claims the tight candidate before any outer shell. A later larger candidate is skipped with `duplicate_outer_composite_media_bbox` when it almost fully contains an already selected composite media bbox.

This keeps the real media block draggable while avoiding a lower raster layer for header/tab chrome.

## Regression Guard

`backend/tests/test_evidence_grounded_dsl_materialization.py` adds `test_composite_media_prefers_tight_inner_candidate_over_outer_chrome_shell`, which constructs nested composite candidates and asserts that only the tight inner media is materialized.

## Validation Evidence

```bash
cd backend
uv run pytest tests/test_evidence_grounded_dsl_materialization.py -q
# 39 passed

uv run pytest tests/test_evidence_grounded_dsl_materialization.py tests/test_m30_upload_pipeline.py tests/test_m37_hierarchy_readiness.py tests/test_hierarchy_materialization.py tests/test_config_env.py -q
# 63 passed

uv run pytest -q
# 236 passed

cd ..
pnpm run check
git diff --check
```

Manual artifact validation on the sample after backend restart:

```text
new task: task_084e65ba247d
materialized composite: refined_0018 [18,236,817,241]
skipped composite: refined_0028 duplicate_outer_composite_media_bbox [18,173,817,304]
top tab text bboxes have no overlapping non-fallback image/composite layer
M38 absolutePositionViolationCount=0
```

## Prevention Notes

Composite media selection must preserve one raster owner per physical media area. Do not accept nested raster candidates independently unless there is a stronger ownership contract proving they represent different visible layers.
