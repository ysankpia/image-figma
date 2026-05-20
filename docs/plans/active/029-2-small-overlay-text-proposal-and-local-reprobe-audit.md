# M29.2 Small Overlay Text Proposal And Local Reprobe Audit

- 状态：active
- 日期：2026-05-20

## Goal

M29.2 audits small overlay text that is visible in the source PNG but missed by global OCR, especially tiny counters inside accepted image regions.

The source chain remains one-way:

```text
source PNG + OCR boxes + M29/M29.0.2 accepted images
-> small overlay text proposal audit
-> optional local crop OCR re-probe
-> m29_2 report, markdown, and development debug assets
```

M29.2 does not materialize text. Even if local re-probe recognizes a counter-like string, the report keeps `materializationEligible=false`.

## Plan

- Add `backend/app/small_overlay_text_proposal.py`.
- Scan only stable M29.0.2 media evidence:
  - `decision == accepted_image`
  - `source == m29_image`
  - `suggestedNextAction == keep_accepted_image`
- Detect small high-contrast component groups near accepted image edges.
- Rank candidates fairly per accepted image before applying the global candidate cap.
- Treat large `baselineSpread` as a penalty for tiny overlay candidates instead of a hard rejection.
- Deduplicate candidates already covered by OCR boxes.
- Write `small_overlay_text_candidates.json` and `.md` under `m29_2/`.
- In development profile, write overlay PNG and candidate crop assets.
- Add `upscale_pixels_nearest(...)` to `png_tools.py` for local crop re-probe.
- Add optional local OCR re-probe behind `M29_SMALL_OVERLAY_TEXT_REPROBE_ENABLED=false`.
- Insert M29.2 after M29.0.2 and before M29.0.3 in the upload pipeline.
- Keep M29.2 optional by default: failures write stage timing/error logs but do not block M30 unless strict mode is enabled.

## Non-Goals

- No OCR JSON rewrite.
- No M29 `nodes.json` rewrite.
- No M29.0.2/0.3/0.4/0.5 contract changes.
- No M30 DSL or fallback erasure changes.
- No M31 or M37 changes.
- No visible text or icon layer creation.
- No business words, fixed page coordinates, fixed viewport rules, or hardcoded `1/6` / `1/9` logic.

## Output

```text
backend/storage/m30_1_uploads/{taskId}/m29_2/
  small_overlay_text_candidates.json
  small_overlay_text_candidates.md
  overlays/small_overlay_text_candidates.png   # development only
  assets/candidates/*.png                      # development only
  assets/upscaled/*.png                        # development + re-probe only
```

The report summary keeps these guardrails stable:

```text
materializedTextCount = 0
createdNewBBoxCount = 0
dslChanged = false
```

## Acceptance

- OCR-missed small overlay counters inside accepted image regions can be reported as `proposal_only`.
- Later accepted images are not starved by earlier noisy images.
- Existing OCR-covered counters are reported as `covered_by_existing_ocr`, not promoted again.
- Texture-like line groups and center photo noise are rejected or absent.
- Optional re-probe can record `reprobe_recognized`, `reprobe_unrecognized`, or `reprobe_failed` without mutating the main OCR artifact.
- Production profile writes JSON/MD only; development profile writes debug images.
- M30, M31, M37, Renderer, and Figma visible output remain unchanged.

## Verification

```bash
cd backend
uv run pytest \
  tests/test_png_tools.py \
  tests/test_small_overlay_text_proposal.py \
  tests/test_m30_upload_pipeline.py \
  tests/test_config_env.py -q
```
