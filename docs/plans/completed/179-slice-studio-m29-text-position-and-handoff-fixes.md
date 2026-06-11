# 179 Slice Studio M29 Text Position And Handoff Fixes

Status: completed

## Goal

Fix the current Pencil/Figma handoff defects without adding sample-specific offsets:

- keep transparent `subject` and `card` slice holes from exposing a white frame background;
- normalize default slice names after delete/add cycles while preserving user names;
- use M29 physical evidence as text bbox authority while OCR remains the text-content authority.

## Implementation

- Add default slice-name normalization on save/export. Only names matching the built-in `slice_<number>` pattern are rewritten.
- Make remainder knockout mask-aware. Rect slices still clear the whole bbox; subject/card slices clear only pixels that are visible in the generated slice PNG.
- Add an M29 text locator in Slice Studio that calls the existing Go `m29extract` binary. It matches OCR lines with M29 text/foreground primitives and feeds the chosen physical bbox into text reconstruction.
- Keep M29 evidence diagnostic-only. It must not create visible raster layers or override `manual_slices.v1.json`.

## Validation

- Slice Studio unit tests for default name normalization, transparent slice knockout, and M29/OCR bbox selection.
- Slice Studio build/typecheck/test.
- Real P1 export inspection using `/Users/luhui/Downloads/project_mq8plzjo_257c14b7-project (4)/assets/originals/P1.png` when local OCR/M29 credentials and project state allow it.

## Result

- Slice Studio `check` and production `build` passed.
- Go M29 tests passed for `./internal/m29/... ./cmd/m29extract`.
- Real P1 verification produced 48 editable text layers: 46 from M29 foreground bbox and 2 from local foreground refinement; duplicate default slice names were eliminated.
