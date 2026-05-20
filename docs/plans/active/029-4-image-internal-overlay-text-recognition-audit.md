# M29.4 Image Internal Overlay Text Recognition Audit

- 状态：completed
- 日期：2026-05-21

## Goal

M29.4 recognizes text inside M29.3 parent-bound image internal overlays as audit-only evidence.

It answers one narrow question:

```text
Can this M29.3 text-like image-internal overlay be safely recognized as a short counter?
```

## Plan

- Add `M294ImageInternalOverlayTextRecognitionDocument v0.1`.
- Consume source PNG, M29.2 small overlay candidates, and M29.3 image internal overlays.
- Require a matching M29.2 candidate for every attempted M29.3 overlay.
- Keep local OCR re-probe disabled by default.
- When re-probe is explicitly enabled, crop the overlay, upscale it with nearest-neighbor, run local OCR, and accept only `^[0-9]{1,2}/[0-9]{1,2}$`.
- Keep `materializationEligible=false`, `materializedTextCount=0`, `createdNewBBoxCount=0`, and `dslChanged=false`.

## Non-Goals

- No OCR JSON mutation.
- No M29, M29.2, or M29.3 artifact mutation.
- No M30 DSL mutation.
- No parent image asset cleanup.
- No visible Figma text layer creation.
- No business text, app name, fixed page coordinate, or sample-specific rule.

## Acceptance

- M29.4 writes `m29_4/image_internal_overlay_text_recognition.json` and `.md` in upload tasks.
- Production profile writes JSON/MD only.
- Development profile also writes overlay and crop debug PNGs.
- Re-probe disabled produces audit items without OCR provider calls.
- Re-probe enabled can mark narrow counter text as `promotion_ready`.
- M30 DSL and M37 output remain unchanged.

## Verification

```bash
cd backend
uv run pytest tests/test_image_internal_overlay_text_recognition.py tests/test_image_internal_overlay.py tests/test_small_overlay_text_proposal.py tests/test_m30_upload_pipeline.py tests/test_config_env.py -q
cd backend && uv run pytest -q
cd ..
pnpm run check
git diff --check
```
