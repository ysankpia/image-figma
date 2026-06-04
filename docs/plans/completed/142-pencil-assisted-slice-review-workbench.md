# 142 Pencil Assisted Slice Review Workbench

Status: completed

## Summary

Upgrade the Plan 141 assisted slice review path from a basic engineering canvas into a browser-usable workbench:

```text
browser upload
-> slice project
-> pan/zoom Canvas review
-> candidate filtering
-> fast manual slice editing
-> manual_slices.v1.json
-> project.zip + selected-assets.zip
```

The product truth source remains `manual_slices.v1.json`. Automatic evidence from PSD-like, M29, OCR, and foreground audit is still candidate/debug input only. This plan does not change automatic ownership arbitration.

## Scope

- Add a browser upload entry page:

```text
GET /api/pencil/slice-projects/new
```

- Improve the existing review page:

```text
GET /api/pencil/slice-projects/{projectId}/review
```

- Keep the implementation in plain HTML, Canvas, and native JavaScript. Do not introduce React, Vue, or a frontend build chain.
- Preserve source-image coordinate truth. Screen coordinates, pan, and zoom are view state only; saved slice bboxes remain source image coordinates.
- Add backend export protection for zero selected slices.

## Required Workbench Behavior

Upload entry:

```text
upload 1..N images
projectName input
boundarySource select with psdlike default
includeDebug checkbox default true
create project via POST /api/pencil/slice-projects
redirect to returned reviewUrl
show backend errors inline
```

Canvas review:

```text
zoom in
zoom out
fit to screen
100%
mouse wheel zoom
pan by dragging
space + drag pan
candidate selection
manual box drawing
moving
8-handle resizing
deleting
renaming
save
export
download link
```

Candidate controls:

```text
candidate visibility toggle
selected slice visibility toggle
kind filters: image/icon/text/shape/group/unknown
source filters: psdlike/m29/foreground_audit/source/manual
minimum confidence control
candidate opacity control
candidate label toggle
default visible kinds: image/icon/group/shape/unknown
text candidates default hidden
```

Editing controls:

```text
Delete or Backspace deletes selected slice
arrow keys move selected slice by 1 px
Shift + arrow keys move selected slice by 10 px
Cmd/Ctrl + S saves
Cmd/Ctrl + D duplicates selected slice
Esc cancels draw or clears selection
double-click candidate creates selected slice
drawing and dragging show live x/y/w/h
page list shows selected count
selected list supports kind, selected, name, bbox editing
list click focuses the slice
```

Export controls:

```text
export auto-saves first
save failure blocks export
zero selected slices returns 409
export success shows reusable download link
```

## Non-Goals

- Do not modify automatic ownership rules.
- Do not make YOLO mandatory.
- Do not implement direct Figma generation.
- Do not restore Codia product routes.
- Do not add Auto Layout reconstruction.
- Do not make transparent export the default.
- Do not modify `services/pencil-go` or the Figma plugin.
- Do not add sample-specific logic based on file path, file name, visible text, brand, fixed coordinates, or screen size.

## Interfaces

New:

```text
GET /api/pencil/slice-projects/new
```

Existing, improved:

```text
GET  /api/pencil/slice-projects/{projectId}/review
POST /api/pencil/slice-projects/{projectId}/export
```

`POST /export` must reject zero selected slices:

```text
409 no selected slices to export
```

## Validation

Required commands:

```bash
cd services/pencil-python-backend
make check
git diff --check
```

API tests:

```text
GET /api/pencil/slice-projects/new returns HTML
create one-image project
create three-image project
export before saved manual_slices returns 409
saved manual_slices with zero selected slices returns 409
selected manual_slices export succeeds
selected-assets.zip contains only selected slice PNGs and manifest.json
project.zip .pen image refs avoid source.png/raw-crops/masks/debug/absolute paths/../
```

Real smoke:

```text
/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png
```

Smoke output:

```text
/Volumes/WorkDrive/pencil-exports/assisted-slice-workbench-smoke-YYYYMMDD-HHMMSS
```

Required smoke signals:

```text
badRefs=0
missingRefs=0
selectedAssetCount == selected slice count
selected-assets.zip only contains selected assets and manifest.json
debug/pages/page_0001/candidates_overlay.png exists
```

Chrome DevTools validation:

```text
open /api/pencil/slice-projects/new
upload sample or create project by script if file upload automation is unstable
open reviewUrl
verify source image renders
verify fit/100%/zoom/pan
verify boxes do not drift after zoom/pan
verify candidate filters
verify double-click candidate adds slice
verify manual draw creates slice
verify drag/resize/delete/rename
verify keyboard save
verify export shows download link
save screenshot to smoke output
```

If Chrome DevTools MCP is unavailable after reasonable repair attempts, record the failed browser validation explicitly and do not claim browser validation passed.

## Implementation Notes

Implemented as a plain HTML + Canvas workbench served by the Pencil Python Backend:

```text
GET /api/pencil/slice-projects/new
GET /api/pencil/slice-projects/{projectId}/review
```

The upload entry creates a slice project from 1..N images, keeps `boundarySource=psdlike` as the default, preserves `includeDebug=true`, and redirects to the review URL. Both upload and review pages include a data favicon so browser validation is not polluted by `/favicon.ico` 404s.

The review workbench now keeps source-image coordinates as the saved truth and treats pan/zoom as view state only. It supports fit, 100%, zoom, wheel zoom, pan mode, space-drag pan, candidate filtering, default-hidden text candidates, double-click candidate selection, manual drawing, moving, 8-handle resizing, deletion, duplication, renaming, bbox editing, save, export, and reusable download links.

The move path uses a separate `moveBox()` helper so moving a slice to a page edge preserves width and height. Resize remains the only operation that changes dimensions.

Backend export now rejects zero selected slices:

```text
409 no selected slices to export
```

## Validation Evidence

Static and API checks:

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

Script smoke sample:

```text
/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png
```

Script smoke output:

```text
/Volumes/WorkDrive/pencil-exports/assisted-slice-workbench-smoke-20260605-003248
```

Script smoke summary:

```text
candidateCount=63
selectedCount=5
selectedAssetCount=5
projectZipEntries=30
hasCandidateOverlay=true
badRefs=0
missingRefs=0
```

Final Chrome DevTools MCP validation used the same sample through the browser upload entry:

```text
http://127.0.0.1:8100/api/pencil/slice-projects/new
```

Final browser project:

```text
slice_20260604165818_24e5b94977
```

Chrome validation signals:

```text
candidateCount=63
filteredCandidateCount=63
defaultTextVisible=false
fit zoom=36%
100% zoom=100%
selectedCount=3
move-to-edge preserves width/height=true
downloadStatus=200
downloadContentType=application/zip
dynamicInputsMissingNames=0
console messages=0
network core requests=200
```

Final Chrome screenshot:

```text
/Volumes/WorkDrive/pencil-exports/assisted-slice-workbench-smoke-20260605-003248/chrome-workbench-review-final-latest.png
```

Final Chrome ZIP:

```text
/Volumes/WorkDrive/pencil-exports/assisted-slice-workbench-smoke-20260605-003248/chrome-download-final-latest.zip
```

Final ZIP audit:

```text
entryCount=24
selected-assets.zip entries:
  manifest.json
  page_0001/0001_slice_1.png
  page_0001/0002_slice_1_copy.png
  page_0001/0003_slice_3.png
badRefs=0
missingRefs=0
```

## Remaining Risk

This closes the browser-assisted slicing path, not automatic semantic reconstruction. Candidate boxes can still be imperfect; the intended product behavior is that the user confirms or edits slices before export, and `manual_slices.v1.json` remains the final delivery contract.
