# Plan 185: Slice Studio dense PC text ownership arbiter

Status: completed
Created: 2026-06-12
Completed: 2026-06-12

## Direction Contract

Slice Studio remains the current product mainline. Saved slices are export truth. OCR and M29 are evidence for editable text handoff, not final visible ownership.

## Problem

Dense PC/Web UI screenshots can generate hundreds of OCR/M29 text layers. The current exporter accepts each line independently, then stacks:

```text
remainder
+ saved slice images
+ visible editable OCR text layers
```

On dense PC UI, this creates repeated text, inflated text, and visual pollution in Pencil even when the `.pen` structure is valid.

## Input Normalization

- User-provided inputs:
  - Dense PC UI Pencil export bug report in `docs/bugs/open/024-slice-studio-dense-pc-ui-pencil-layer-coordination.md`.
  - Gemini proposal about M29/OCR padding, font sizing, knockout, and spatial arbitration.
  - Local history from plans 114/115 and bugs 021/023.
- Truth sources:
  - Current Slice Studio export code in `apps/slice-studio/server`.
  - Current tests in `apps/slice-studio/tests/pencil-exporter.test.ts`.
- Evidence/candidate sources:
  - Historical clean-editable / visual-fidelity / visual-ocr mode contracts.
  - Old visual text rejection bug record.
- Missing inputs:
  - None for a first gated implementation.
- Final output:
  - A mainline text ownership gate that only emits visible editable text when the line is safe enough for Pencil replay.

## Scope

In scope:

- Add a text ownership/classification gate in `apps/slice-studio/server/text-reconstruction.ts`.
- Keep high-confidence normal UI text editable.
- Preserve raster ownership for lines that are covered by confirmed slices or are too dense/small/fragmentary for safe replay.
- Add regression tests proving dense tiny PC text is not promoted to visible Pencil text while normal text still is.
- Update bug/progress docs with evidence.

Out of scope:

- Per-M29 crop OCR.
- OCR provider changes.
- AI slice prompt changes.
- Database/schema/API changes.
- Frontend UI changes.
- Reviving old Python/Go Pencil services.
- Full automatic design reconstruction.

## Progress Checkpoints

- `PROGRESS.md` update required: yes.
- Module validation cadence: run focused unit tests after text reconstruction changes.
- E2E/artifact validation target: run Slice Studio check/build; real dense sample export if local server/data/credentials are available.

## Validation

```bash
pnpm --dir apps/slice-studio exec vitest run tests/pencil-exporter.test.ts
pnpm --dir apps/slice-studio run check
pnpm --dir apps/slice-studio run build
git diff --check
git status --short --branch
```

## Completion Criteria

- Dense tiny/fragmentary PC UI text can be classified as raster-preserved and does not produce a visible text node.
- Normal OCR text remains editable and knocked out from the remainder.
- Existing Slice Studio tests pass.
- Bug 024 records the implemented first fix and residual risk.

## Result

- Added `slice_studio_text_ownership.v1` to Slice Studio text reconstruction.
- OCR/M29 text lines now make an explicit ownership decision before becoming visible Pencil text:
  - `editable_text` becomes a visible TextLayer and participates in text knockout;
  - `raster_preserve` stays in the raster/remainder path and does not create a visible TextLayer;
  - `skipped` is counted but not emitted.
- M29 physical text matches that are too broad for the OCR line now fall back to OCR bbox before font sizing.
- Shared M29 physical boxes used by multiple OCR lines are demoted to OCR bbox.
- Local foreground refinement also rejects over-broad physical boxes before using them for font sizing.
- Dense text pages suppress tiny OCR lines and generated marker labels such as `img-11`, `Ing-01`, and `g-16` as raster-preserved evidence.
- Manifest OCR metadata now records `rasterPreservedTextCount`, `skippedTextCount`, and `ownershipPolicy`.

## Validation Evidence

```bash
pnpm --dir apps/slice-studio exec vitest run tests/pencil-exporter.test.ts
pnpm --dir apps/slice-studio run check
pnpm --dir apps/slice-studio run build
git diff --check
```

Results:

```text
tests/pencil-exporter.test.ts: 18 passed
pnpm check: 8 test files / 54 tests passed
pnpm build: Next.js production build passed
git diff --check: passed
```

Real sample smoke:

```text
POST /api/projects/project_mqar9qpo_93b911d9/export-project
assetCount: 36
pageCount: 2
```

Dense PC page after fix:

```text
sourceLineCount: 219
textLayerCount: 116
rasterPreservedTextCount: 103
skippedTextCount: 0
ownershipPolicy: slice_studio_text_ownership.v1
```

Control examples:

```text
Undo       26.2 -> 9.8
QFit 100%  19.3 -> 10.5
Pan        27.1 -> 16.1
Zoom In    28.5 -> 14.7
Zoom Out   28.5 -> 17.5
```

Pencil MCP screenshot of `page_0001__frame` was inspected from the regenerated `design.pen`. The dense PC page no longer shows the previous layer-wide OCR text pollution; generated blue marker labels and tiny dense text are no longer emitted as visible editable text layers.
