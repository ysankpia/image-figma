# 180 Slice Studio Text Node Render Box Fix

Status: completed

## Problem

Latest exported Pencil package still shows text size and apparent offset issues even when M29/local foreground bbox evidence is present. The concrete package `/Users/luhui/Downloads/project_mq8plzjo_257c14b7-project (6)` has:

- OCR provider `baidu_ppocrv5`;
- bbox provider `m29_ocr_hybrid`;
- 48 text layers;
- no duplicate default slice names.

The remaining defect is not missing M29 evidence. It is text rendering: generated `.pen` text nodes use `textGrowth: "fixed-width-height"` plus `textAlignVertical: "middle"`, so Pencil/Figma line-height behavior can move glyphs inside an expanded safe box. Package `(6)` also came from the temporary oversized physical-bbox font formula, which made prices, bottom navigation labels, and product titles too large.

## Scope

- Keep OCR as text-content authority.
- Keep M29/local foreground as physical bbox authority.
- Keep manual slices as final raster asset authority.
- Do not add global offsets or sample-specific coordinates.
- Do not structure buttons or cards.

## Plan

1. Keep the conservative physical-bbox font sizing formula.
2. Emit Pencil text nodes with `textGrowth: "auto"` and no fixed `width`, fixed `height`, or vertical middle alignment.
3. Use the physical/original bbox as the visual anchor for text placement, while keeping the expanded safe bbox and source bbox in metadata/manifest. The bbox is evidence and erase policy, not a wrapping box.
4. Add a regression test that exported text nodes do not use fixed-height vertical centering.
5. Re-export the real P1 project, inspect manifest values, open the generated `design.pen` in Pencil, and verify the screenshot.

## Validation

## Result

- `(6)` was confirmed to be a temporary oversized font export: product title `31.6`, price `27.5`, bottom nav label `20.4`.
- Conservative font sizing produces product title `28.5`, price `22.1`, bottom nav label `16.4`.
- `fixed-width` was tested and rejected because tight physical bboxes wrap short labels and prices.
- Final `.pen` editable text uses `textGrowth: "auto"` with no fixed `width`, no fixed `height`, and no vertical centering.
- `safeBBox` remains in metadata and is used only for raster text erase policy.

## Validation

```bash
pnpm --dir apps/slice-studio run check
pnpm --dir apps/slice-studio run build
git diff --check
```

Real export validation:

```text
/tmp/project-mq8-text-auto-fix/unzipped/design.pen
```

Pencil screenshots were inspected for `page_0001__frame` and `page_0002__frame`.
