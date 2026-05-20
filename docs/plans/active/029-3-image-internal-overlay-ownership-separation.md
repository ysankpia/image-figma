# M29.3 Image Internal Overlay Ownership Separation

- 状态：completed
- 日期：2026-05-21

## Goal

M29.3 records explicit parent-bound overlay evidence inside M29.0.2 accepted images.

The source problem is ownership, not OCR text recognition: an accepted image can contain both a bitmap base and small UI overlay marks. M29.3 expresses that as audit-only evidence:

```text
accepted image evidence + source pixels -> image internal overlay ownership report
```

## Plan

- Add `M293ImageInternalOverlayDocument v0.1`.
- Scan only M29.0.2 `accepted_image` media evidence with `source=m29_image` and `suggestedNextAction=keep_accepted_image`.
- Reuse the M29.2 high-contrast edge overlay detector and fair per-image selection.
- Bind each overlay to both `sourceImageNodeId` from M29.0.2 and `sourceM29NodeId` from M29.
- Record OCR de-duplication, anchor, overlay kind, reasons, and metrics.
- Keep `materializationEligible=false`, `materializedTextCount=0`, `createdNewBBoxCount=0`, and `dslChanged=false`.

## Non-Goals

- No OCR JSON mutation.
- No M29 nodes mutation.
- No M30 supplemental materialization.
- No fallback erasure change.
- No M31/M37/Renderer visible output change.
- No `1/6`, slash, page-coordinate, app, or business-word special casing.

## Acceptance

- M29.3 writes `m29_3/image_internal_overlays.json` and `.md` in upload tasks.
- Production profile writes JSON/MD only.
- Development profile also writes overlay and crop debug PNGs.
- Existing OCR-covered overlays are marked `covered_by_existing_ocr`, not promoted.
- Later accepted images are not starved by earlier noisy image regions.
- Current sample's `m29_image_003` can produce a parent-bound `text_like_overlay_candidate` near the known top-right overlay area.

## Verification

```bash
cd backend
uv run pytest tests/test_image_internal_overlay.py tests/test_small_overlay_text_proposal.py tests/test_m30_upload_pipeline.py tests/test_config_env.py -q
cd backend && uv run pytest -q
cd ..
pnpm run check
git diff --check
```
