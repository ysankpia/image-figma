# M30.5 Image-Internal Overlay Text Promotion And Parent Cleanup

- 状态：completed
- 日期：2026-05-21

## Goal

M30.5 consumes M29.4 `promotion_ready` image-internal overlay text evidence and turns it into:

```text
cleaned parent image asset + editable DSL text node
```

The stage exists because M29.4 is recognition audit only. It proves a parent-bound overlay can be read, but it does not clean the parent bitmap or create visible text.

## Plan

- Add a M30.5 upload stage after `m30_materialization` and before `m30_asset_publish`.
- Read `m29_4/image_internal_overlay_text_recognition.json` and only accept items with `decision=promotion_ready`, non-empty `recognizedText`, tight `recognizedTextBBox`, and `recognized_bbox_from_local_ocr`.
- Resolve the parent image asset from an existing M30 image node, matching M29.0.5 visual asset, or matching M29.0.2 accepted image.
- Copy the parent image asset, erase only glyph pixels mapped from `recognizedTextBBox`, and keep the original asset unchanged.
- Add a cleaned parent image asset to DSL assets and either retarget the existing parent image node or create a new parent image node.
- Add an editable `m30_image_internal_overlay_text` DSL text node above the cleaned parent image.
- Default to `maxPromotions=1` for the first release.

## Non-Goals

- No M29.2, M29.3, or M29.4 mutation.
- No OCR re-run and no M29.4 performance optimization.
- No direct `overlayBBox` erasure.
- No original asset mutation.
- No batch promotion by default.
- No dark-on-light or complex inpainting support.

## Acceptance

- M30.5 writes `m30_5/image_internal_overlay_promotion_report.json` and `.md`.
- M30.5 creates cleaned parent assets under `m30/assets/m30_image_internal_overlay_cleaned/`.
- A safe `promotion_ready` item creates one editable `m30_image_internal_overlay_text` node.
- Parent image cleanup preserves the original parent asset and only writes a cleaned copy.
- M30 asset publishing rewrites cleaned asset URLs to `/files/assets/{taskId}/m30/...`.

## Verification

```bash
cd backend
uv run pytest tests/test_image_internal_overlay_promotion.py tests/test_image_internal_overlay_text_recognition.py tests/test_m30_upload_pipeline.py tests/test_config_env.py -q
cd backend && uv run pytest -q
cd ..
pnpm run check
git diff --check
```
