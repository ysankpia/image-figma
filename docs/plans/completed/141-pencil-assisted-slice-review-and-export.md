# 141 Pencil Assisted Slice Review And Export

Status: completed

## Summary

Make assisted slice review the next Pencil Python Backend product path:

```text
1..N images
-> automatic slice candidates
-> HTML Canvas review
-> manual_slices.v1.json
-> Pencil project.zip + selected-assets.zip
```

The product truth source is `manual_slices.v1.json`. M29, PSD-like, OCR, and foreground ownership audit are candidate sources only; they do not decide final export.

## Key Changes

- Add slice-project HTTP routes beside the existing `/api/pencil/projects` export API.
- Generate `pencil.slice_candidates.v1` from source-image geometry and available backend evidence.
- Serve a simple Canvas review page for selecting, drawing, moving, resizing, deleting, and naming slices.
- Persist `pencil.manual_slices.v1` and export only selected manual slices.
- Generate a Pencil `project.zip` and a `selected-assets.zip` with page-namespaced crop assets.

## Interfaces

```text
POST /api/pencil/slice-projects
GET  /api/pencil/slice-projects/{projectId}
GET  /api/pencil/slice-projects/{projectId}/review
GET  /api/pencil/slice-projects/{projectId}/candidates
PUT  /api/pencil/slice-projects/{projectId}/manual-slices
POST /api/pencil/slice-projects/{projectId}/export
GET  /api/pencil/slice-projects/{projectId}/download.zip
```

Contracts:

```text
pencil.slice_candidates.v1
pencil.manual_slices.v1
```

## Validation

- `cd services/pencil-python-backend && make check`
- `git diff --check`
- API tests for create, candidates, review, manual-slices, export, download, and error cases.
- Real smoke with `/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png`.
- Open exported `clean-editable/design.pen` in Pencil and confirm selected slices are independently draggable and positioned 1:1.

## Non-Goals

- No Codia-like full reconstruction.
- No H5 reconstruction.
- No direct Figma generation.
- No YOLO mandatory semantic chain.
- No Auto Layout reconstruction.
- Transparent background remains optional and must not degrade default rect export.

## Implementation Notes

Implemented in `services/pencil-python-backend` as a separate assisted slice API:

```text
POST /api/pencil/slice-projects
GET  /api/pencil/slice-projects/{projectId}
GET  /api/pencil/slice-projects/{projectId}/review
GET  /api/pencil/slice-projects/{projectId}/candidates
GET  /api/pencil/slice-projects/{projectId}/manual-slices
PUT  /api/pencil/slice-projects/{projectId}/manual-slices
POST /api/pencil/slice-projects/{projectId}/export
GET  /api/pencil/slice-projects/{projectId}/download.zip
```

Core files:

```text
services/pencil-python-backend/app/slice_projects.py
services/pencil-python-backend/app/routes/slice_projects.py
services/pencil-python-backend/app/main.py
```

The implementation deliberately keeps automatic evidence non-authoritative:

```text
PSD-like/M29/OCR/foreground audit -> candidates.v1.json
saved manual_slices.v1.json -> only export truth source
```

Create writes an empty `manual_slices.v1.json` for the review UI, but export is blocked until the user saves manual slices through `PUT /manual-slices`. This is tracked by `manualSlicesConfirmed=true`.

Canvas Review v1 supports:

```text
page switching
candidate selection
manual box drawing
moving
8-handle resizing
deleting
renaming
saving
exporting
download link
```

Export behavior:

```text
selected slices crop from pages/page_XXXX/source.png
clean-editable/design.pen uses exact source coordinates
visual-fidelity/design.pen uses exact source coordinates
visual-ocr/design.pen uses exact source coordinates
selected-assets.zip contains only selected slice PNGs and manifest.json
project.zip excludes raw selected-assets/ directory but includes selected-assets.zip
debug/pages/page_XXXX includes source, candidates, manual_slices, overlay, candidates_overlay
```

## Local Validation Evidence

Checks passed:

```bash
cd services/pencil-python-backend
make check
```

Result:

```text
31 passed, 2 warnings
```

Targeted API validation:

```text
create slice project
fetch review page
fetch candidates
reject export before manual save
save manual_slices
export
download project.zip
validate selected-assets.zip contents
reject out-of-bounds bbox
reject missing files
reject invalid image
return 404 for missing project
multi-image project creates page_0001/page_0002/page_0003
```

Real sample smoke used:

```text
/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png
```

Smoke output:

```text
/Volumes/WorkDrive/pencil-exports/assisted-slice-smoke-20260604/project.zip
/Volumes/WorkDrive/pencil-exports/assisted-slice-smoke-20260604/summary.json
```

Smoke summary:

```text
candidateCount=63
selectedCount=5
selectedAssetCount=5
projectZipEntries=29
badRefs=0
missingRefs=0
```

`selected-assets.zip` contained:

```text
page_0001/0001_smoke_0001.png
page_0001/0002_smoke_0002.png
page_0001/0003_smoke_0003.png
page_0001/0004_smoke_0004.png
page_0001/0005_smoke_0005.png
manifest.json
```

The prompt-mentioned Downloads path was not present locally:

```text
/Users/luhui/Downloads/Screenshot - 腾讯动漫_018_1440.png.png
```

The matching local sample under `/Users/luhui/Downloads/figma/image/` was used instead.

## Remaining Risk

V1 is intentionally a mechanical assisted slicing product path. It does not solve automatic semantic reconstruction. Candidate quality can still be imperfect; that is acceptable because the saved manual slice contract is the final truth source.
