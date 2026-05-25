# 055 M29 Internal Asset Evidence and Cleanup Hardening

## Status

completed

## Objective

Fix the current M29 internal asset chain gap exposed by real upload `task_8d5806b08f44`: internal media foreground is partially detected and promoted, but too much evidence depends on OCR anchors, transparent cutouts can retain local background, and promoted internal assets do not yet have a complete parent-media cleanup path.

## Scope

Allowed:

- `backend/app/media_internal_decomposition/`
- `backend/app/transparent_asset_report/`
- `backend/app/internal_source_promotion/`
- `backend/app/m29_replay_plan/`
- `backend/app/plan_materializer/`
- focused backend tests for those packages and upload pipeline
- M29 contract docs, bug record, and current code map

Forbidden:

- DSL schema changes
- public API response shape changes
- Renderer or Figma plugin special cases
- file name, text literal, industry, theme color, fixed bbox, or single-screenshot rules
- Auto Layout, Component/Instance, Variant, Vectorization, or Figma variable materialization

## Acceptance Criteria

- M29.6 can report non-OCR internal foreground components from composite media pixels.
- OCR anchor remains a relation hint, not the only foreground discovery source.
- Transparent asset extraction produces cleaner icon alpha and rejects assets with high edge/background alpha risk.
- Promotion permission continues to require M29.6 accepted candidates plus transparent asset allow; medium candidates may pass only with structural support.
- Promoted internal assets get M29.5-authorized copied media cleanup when contained by their parent media.
- Materializer consumes only M29.5 cleanup authorization for promoted internal asset erasure.
- Existing upload `/dsl` API shape remains unchanged.
- Regression tests cover the new evidence and cleanup contracts.

## Validation

Run at least:

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
git diff --check
```

If time permits, run the latest real-image upload artifact path or full backend tests.

## Completion Notes

Completed on 2026-05-25.

Implemented:

- M29.6 now reports non-OCR internal foreground components inside preserve-raster media, while keeping OCR text masks and hero/texture rejection gates.
- Transparent asset extraction now reports edge-alpha metrics and rejects candidates with high edge/background alpha residue.
- M29 internal source promotion now uses execution-supported language: high confidence or structurally supported medium confidence.
- M29.5 now authorizes copied media asset cleanup for promoted internal assets only when parent media source evidence and M29.3 relation support containment.
- Materializer now executes promoted internal asset cleanup only from M29.5 cleanup targets and uses transparent asset alpha masks when erasing the copied parent media asset.

Validation:

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
```

Result:

```text
60 passed
```
