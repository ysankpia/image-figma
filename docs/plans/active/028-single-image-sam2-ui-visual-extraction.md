# M28 Single-Image SAM2 UI Visual Extraction Harness

## Summary

M28 adds a single-image SAM2 UI visual extraction harness for the fixed complex commerce screenshot:

```text
/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png
```

M28 is not upload pipeline, not DSL mutation, not Figma visible replay, and not batch processing. It produces evidence artifacts that separate usable UI visual objects into:

- `icons/*.png`: real UI icons such as location, search, announcement, tool icons and bottom navigation icons.
- `images/*.png`: whole image assets such as hero/banner images, category product images, product photos and supplier product images.
- `controls/*.png`: icon plus control/background objects such as message badge, plus buttons and cart buttons.
- `blocked`: text, numeric labels, card/background fragments, status bar and image-internal SAM2 fragments.

## Implementation

Code:

```text
backend/app/ui_visual_extraction.py
backend/scripts/run_m28_single_visual_extraction.py
backend/tests/test_ui_visual_extraction.py
```

Default output:

```text
backend/storage/m28_single_visual_extraction/
  icons/*.png
  images/*.png
  controls/*.png
  m28_visual_extraction.json
  m28_visual_extraction_overlay.png
  m28_visual_extraction_preview_sheet.png
```

The harness uses the existing uv `perception-sam2` environment and the external checkpoint:

```text
/Volumes/WorkDrive/Models/sam2/sam2.1_hiera_tiny.pt
```

The checkpoint remains outside tracked files.

## Behavior

SAM2 raw masks are proposals, not truth. M28 first creates image asset protection zones, then classifies remaining visual objects. This is the key difference from M25/M27:

- M25/M27 page-specific exclusions such as `bed_map_zone` and `illustration_zone` are not used.
- Hero/banner/product photo areas are accepted as whole image assets.
- SAM2 fragments inside accepted image assets are blocked with `inside_image_asset`.
- Text-like, line-like, red digit/badge-like and background-like masks are blocked.
- Stable mobile-commerce layout probes fill obvious UI icon/control gaps when SAM2 does not return a clean mask.

M28 deliberately does not modify:

```text
root.children
DSL assets
DSL meta
Renderer input
visible icon fallback nodes
```

## Run

```bash
cd backend
uv run python scripts/run_m28_single_visual_extraction.py \
  --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png" \
  --checkpoint "/Volumes/WorkDrive/Models/sam2/sam2.1_hiera_tiny.pt" \
  --output-dir "storage/m28_single_visual_extraction"
```

High-quality single-image mode:

```bash
cd backend
uv run python scripts/run_m28_single_visual_extraction.py \
  --quality high \
  --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png" \
  --checkpoint "/Volumes/WorkDrive/Models/sam2/sam2.1_hiera_tiny.pt" \
  --output-dir "storage/m28_single_visual_extraction_high"
```

## Acceptance

The minimum smoke threshold for the fixed image is:

```text
icon/control accepted >= 25
image_asset accepted >= 15
obvious accepted text false positives = 0
obvious hero/product photo internal accepted fragments = 0
```

Current smoke evidence after implementation:

```text
icons=19
controls=11
imageAssets=18
blocked=46
rawMasks=55
device=mps
```

That gives `icon/control accepted = 30` and satisfies the minimum threshold while keeping hero/product internals protected.

## Validation

Required:

```bash
cd backend && uv run pytest tests/test_ui_visual_extraction.py -q
cd backend && uv run pytest
pnpm run check
git diff --check
```

M28 storage output is evidence only and must not be committed.
