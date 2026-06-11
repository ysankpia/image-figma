# 183 Slice Studio AI Tile Merge And Progress

## Summary

Fix two issues found after the first real AI slice smoke:

- Large visual assets can be split into adjacent partial rectangles when they cross six-tile boundaries.
- Batch AI drawing currently reports progress only as toolbar status text, which is not visible enough for long 30-page runs.

Keep the existing contract:

- AI still only draws `rect` slices.
- AI boxes still become normal `SliceRecord` entries through the existing save path.
- Manual slices remain the only export truth source.
- No M29/OCR evidence is passed to the AI slicer.

## Current Evidence

The 7-page `525测试` smoke completed successfully, but overlay inspection showed large assets split near tile boundaries:

- P2 large ring artwork returned overlapping top/bottom partial boxes.
- P4 record artwork returned several stacked large boxes.
- P5/P6 list item imagery produced adjacent partial boxes around row/tile boundaries.

Small icons are less affected because they usually fit inside a single tile.

## Scope

- Experiment with post-tile merge strategies before changing product code.
- Prefer deterministic geometry merge when it improves split assets without merging separate list rows.
- If deterministic merge is too risky, test an AI review pass that sees a compressed full-page overlay and returns revised boxes.
- Add a dismissible/minimizable batch progress overlay in the workbench.

## Non-Goals

- Do not introduce persistent AI proposal state.
- Do not auto-switch to `subject` or `card`.
- Do not hardcode sample names, page ids, visible text, or fixed coordinates.
- Do not change export contracts.

## Acceptance

- Large assets crossing tile boundaries are less likely to be returned as two adjacent boxes.
- Re-running AI on a page still de-dupes against existing manual slices.
- Batch AI shows page progress and added/skipped counts in a visible overlay.
- The overlay can be minimized or dismissed without stopping the batch.
- Existing check/build pass.

## Validation

```bash
pnpm --dir apps/slice-studio run check
pnpm --dir apps/slice-studio run build
git diff --check
```

Real validation should reuse the local 7-image `525测试` set and compare overlays before/after.

Current validation:

- `pnpm --dir apps/slice-studio run check` passed with 8 test files and 50 tests.
- `pnpm --dir apps/slice-studio run build` passed.
- `git diff --check` passed.
- P2/P4 focused smoke confirmed overview review merges large cross-tile artwork into one box.
- Chrome DevTools opened the review workbench, confirmed AI buttons, asset gallery navigation, progress panel, and no console warnings/errors.
- A full local 7-image smoke completed 7/7 pages, failed 0 pages, added 76 slices, skipped 46 boxes, and exported `project.zip` with 7 pages and 76 assets.
- Compared with the previous 109-slice baseline, large cross-tile assets are less fragmented. Remaining redundant boxes are normal AI draft cleanup, not the original tile-split defect.
