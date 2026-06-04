# 143 Assisted Slice Workbench P0 Hardening

Status: completed

## Summary

Harden the assisted slice review workbench from a usable validation page into a safer daily tool:

```text
browser upload
-> candidates
-> fast user confirmation/editing
-> autosaved manual_slices.v1.json
-> project.zip + selected-assets.zip
```

The product truth source remains `manual_slices.v1.json`. Automatic evidence still only produces candidates. This plan does not modify automatic ownership, YOLO arbitration, Codia routes, Figma plugin behavior, or Pencil Go paths.

## P0 Scope

Implement the editing workflow improvements that reduce user mistakes and lost work:

```text
autosave with debounce
undo / redo
hover and active selection clarity
empty canvas click clears selection
page list progress state
page thumbnails
selected slice thumbnail previews
page navigation shortcuts
```

## Required P0 Behavior

Autosave:

```text
manual_slices changes schedule PUT /manual-slices after 500ms
status shows dirty / saving / saved / save failed
export waits for pending autosave or saves immediately before POST /export
refreshing after autosave reloads the saved selected slices
```

Undo / redo:

```text
Cmd/Ctrl+Z undo
Cmd/Ctrl+Shift+Z redo
max 50 snapshots
record manual_slices only
do not record pan/zoom/view state
undo/redo schedule autosave
```

Editing polish:

```text
hover candidate highlights candidate
hover selected slice highlights slice
active selected slice is visually stronger
clicking empty canvas clears selection
drag/draw/resize HUD shows x/y/w/h
```

Batch/page polish:

```text
page list shows small thumbnail
page list shows candidate count
page list shows selected count
page list shows dirty/saved state
Alt/Option + ArrowLeft moves to previous page
Alt/Option + ArrowRight moves to next page
```

Selected asset preview:

```text
right panel shows thumbnail crop for each selected slice
clicking a selected item focuses the slice on canvas
thumbnail uses source image crop in browser canvas, not an extra backend API
```

## Non-Goals

Do not implement in this plan:

```text
automatic ownership repair
YOLO as mandatory semantic chain
direct Figma generation
Codia-like tree reconstruction
Auto Layout reconstruction
transparent export default
Figma plugin changes
services/pencil-go changes
```

## P1 Backlog

Record for a later plan, not this implementation:

```text
candidate recommendation tiers
candidate dedupe/noise scoring
multi-candidate lasso selection
bulk add/remove selected
bulk delete selected
stable user naming policy
selected-assets contact sheet
current-page-only download package
```

## P2 Backlog

Record for a later plan, not this implementation:

```text
transparent-background export mode
AI-assisted slice naming
YOLO-assisted candidate sorting
OCR-assisted text-candidate hiding beyond current filters
collaborative review
cloud project management
```

## Validation

Required checks:

```bash
cd services/pencil-python-backend
make check
git diff --check
```

Required browser validation with Chrome DevTools MCP:

```text
open /api/pencil/slice-projects/new
upload /Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png
confirm review page loads
add a candidate slice
draw a manual slice
move or resize a slice
verify dirty -> saving -> saved status
reload page and verify autosaved slices persist
undo
redo
verify undo/redo affect only manual_slices, not zoom/pan view
verify selected thumbnails render
verify page list thumbnail, candidate count, selected count, save state
export ZIP
validate badRefs=0 and missingRefs=0
verify console messages=0 and core network requests are 200
```

## Acceptance

P0 is complete when:

```text
manual edits no longer require the user to remember pressing Save
mistakes can be undone/redone
selected assets are visually recognizable in the right panel
page status is visible from the left panel
complex sample browser smoke passes
ZIP contract remains clean
```

## Implementation Notes

Implemented in the existing plain HTML + Canvas workbench. No frontend build system, Figma plugin changes, Pencil Go changes, automatic ownership rules, or YOLO semantic chain changes were introduced.

P0 additions:

```text
autosave with 500ms debounce
save status: dirty / autosaving / saved / failed
export waits for pending autosave
Cmd/Ctrl+Z undo
Cmd/Ctrl+Shift+Z redo
50-snapshot manual_slices history
hover candidate / selected slice highlight
empty canvas click clears active selection
page thumbnail, candidate count, selected count, save state
Alt/Option + ArrowLeft / ArrowRight page navigation
selected slice crop thumbnails in the right panel
```

Autosave and undo/redo record only `manual_slices.v1.json` state. Pan, zoom, page viewport, and visual filter state remain view state and are not part of undo history.

## Validation Evidence

Static/API checks:

```bash
cd services/pencil-python-backend
make check
```

Result:

```text
33 passed, 2 warnings
```

Diff hygiene:

```bash
git diff --check
```

Result:

```text
clean
```

Chrome DevTools MCP sample:

```text
/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png
```

Chrome project:

```text
slice_20260604172419_af05812831
```

Browser validation signals:

```text
candidateCount=63
defaultTextVisible=false
afterAddCount=2
dirtyStatus=dirty
savedStatus=saved (2)
savedCountAfterAdd=2
saved manual_slices GET after autosave returned 2 slices
full page reload restored 2 selected slices from manual_slices.v1.json
countAfterUndo=1
savedCountAfterUndo=1
countAfterRedo=2
savedCountAfterRedo=2
single-page pageByOffset(1) stayed on page_0001
thumbCount=2
thumbNonBackgroundPixels=[1512,5292]
page list shows 63 candidates / 2 selected / saved
downloadStatus=200
downloadContentType=application/zip
dynamicInputsMissingNames=0
console messages=0
core network requests=200
```

Chrome screenshot:

```text
/Volumes/WorkDrive/pencil-exports/assisted-slice-p0-hardening-20260605/chrome-p0-workbench.png
```

Chrome ZIP:

```text
/Volumes/WorkDrive/pencil-exports/assisted-slice-p0-hardening-20260605/chrome-p0-download.zip
```

ZIP audit:

```text
entryCount=21
selected-assets.zip:
  manifest.json
  page_0001/0001_slice_1.png
  page_0001/0002_slice_2.png
badRefs=0
missingRefs=0
```

Local server was stopped after validation; no process remained listening on `127.0.0.1:8100`.

## Remaining Risk

This is still an assisted manual review product path. Candidate quality improvements, bulk selection, contact sheets, transparent export, and AI naming remain backlog items for later plans.
