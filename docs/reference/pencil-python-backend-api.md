# Pencil Python Backend API

This is the caller contract for `services/pencil-python-backend`.

It is a Pencil project ZIP export API, not the main Draft runtime API. Do not use this contract for the Figma plugin Draft `/api/draft-preview` path.

## Base URL

Local default:

```text
http://127.0.0.1:8100
```

When reverse proxied, keep the path prefix unchanged:

```text
/api/pencil/projects
```

## Response Shape

Successful JSON responses use:

```json
{
  "success": true,
  "data": {}
}
```

FastAPI validation and explicit backend errors currently return the standard FastAPI error shape:

```json
{
  "detail": "files[] is required"
}
```

Callers must treat non-2xx HTTP status as failure and show `detail` when present.

## Endpoint Summary

```text
GET  /api/health
GET  /api/ready
POST /api/pencil/projects
GET  /api/pencil/projects/{taskId}
GET  /api/pencil/projects/{taskId}/manifest
GET  /api/pencil/projects/{taskId}/download.zip
```

Assisted slice review uses a separate synchronous project API:

```text
GET  /api/pencil/slice-projects
GET  /api/pencil/slice-projects/workspace
GET  /api/pencil/slice-projects/new
POST /api/pencil/slice-projects
GET  /api/pencil/slice-projects/{projectId}
PUT  /api/pencil/slice-projects/{projectId}
POST /api/pencil/slice-projects/{projectId}/clone
DELETE /api/pencil/slice-projects/{projectId}
GET  /api/pencil/slice-projects/{projectId}/review
GET  /api/pencil/slice-projects/{projectId}/candidates
GET  /api/pencil/slice-projects/{projectId}/review-state
PUT  /api/pencil/slice-projects/{projectId}/review-state
GET  /api/pencil/slice-projects/{projectId}/manual-slices
PUT  /api/pencil/slice-projects/{projectId}/manual-slices
POST /api/pencil/slice-projects/{projectId}/export-preview
POST /api/pencil/slice-projects/{projectId}/export
GET  /api/pencil/slice-projects/{projectId}/download.zip
GET  /api/pencil/slice-projects/{projectId}/selected-assets.zip
```

## Health

```text
GET /api/health
```

Success:

```json
{
  "success": true,
  "data": {
    "status": "ok"
  }
}
```

`/api/health` is a liveness check. It only proves the FastAPI process is responding.

## Readiness

```text
GET /api/ready
```

`/api/ready` is the deployment readiness check. It validates runtime imports, writable storage, PSD-like runner path, default boundary source, `m29extract` when required, and OCR configuration visibility.

Ready response:

```json
{
  "success": true,
  "data": {
    "status": "ready",
    "ready": true,
    "checks": [
      {"name": "runtimeImports", "ok": true, "detail": "fastapi,uvicorn,multipart,PIL,numpy,pydantic,requests"},
      {"name": "storageRoot", "ok": true, "detail": "/data/pencil-python-backend"},
      {"name": "psdlikeRunner", "ok": true, "detail": "/opt/pencil-python-backend/services/psdlike-python/tools/run_one.py"},
      {"name": "defaultBoundarySource", "ok": true, "detail": "psdlike"},
      {"name": "m29extract", "ok": true, "detail": "/opt/pencil-python-backend/services/backend-go/bin/m29extract"},
      {"name": "ocr", "ok": true, "detail": "none"}
    ]
  }
}
```

Not ready returns HTTP `503`:

```json
{
  "success": false,
  "data": {
    "status": "not_ready",
    "ready": false,
    "checks": [
      {"name": "psdlikeRunner", "ok": false, "detail": "missing /opt/pencil-python-backend/services/psdlike-python/tools/run_one.py"}
    ]
  }
}
```

Callers and smoke scripts should check `/api/ready` before creating projects.

## Create Project

```text
POST /api/pencil/projects
Content-Type: multipart/form-data
```

Fields:

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `files[]` or `files` | yes | none | 1..`PENCIL_BACKEND_MAX_FILES`; PNG/JPG/JPEG/WEBP only |
| `projectName` | no | `Pencil Project` | Stored in task status and manifest |
| `mode` | no | `all` | `all`, `clean-editable`, `visual-fidelity`, `visual-ocr` |
| `columns` | no | `auto` | `auto` or positive integer |
| `includeDebug` | no | `true` | Include `debug/` artifacts in ZIP |
| `ocrProvider` | no | server `OCR_PROVIDER` | Override OCR provider for this task |
| `boundarySource` | no | server `PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE` | Default is `psdlike`; explicit `m29`, `psdlike`, `hybrid` are supported |

Default production behavior:

```text
boundarySource=psdlike
mode=all
includeDebug=true
```

Success response is immediate. It does not mean the ZIP is ready:

```json
{
  "success": true,
  "data": {
    "taskId": "pencil_20260603211804_6d110631ce",
    "status": "queued",
    "boundarySource": "psdlike"
  }
}
```

Recommended caller behavior:

1. Send `files[]`.
2. Omit `boundarySource` unless you intentionally need `m29` or `hybrid`.
3. Store `taskId`.
4. Poll status until `completed` or `failed`.
5. Download ZIP only after `completed`.

Do not call `/download.zip` immediately after create.

## Get Project Status

```text
GET /api/pencil/projects/{taskId}
```

Status values:

```text
queued
running
completed
failed
```

Queued/running example:

```json
{
  "success": true,
  "data": {
    "taskId": "pencil_20260603211804_6d110631ce",
    "status": "running",
    "projectName": "Project A",
    "pageCount": 3,
    "modes": ["clean-editable", "visual-fidelity", "visual-ocr"],
    "boundarySource": "psdlike",
    "warnings": [],
    "createdAt": "2026-06-03T13:18:04.000000+00:00",
    "updatedAt": "2026-06-03T13:18:05.000000+00:00"
  }
}
```

Completed example:

```json
{
  "success": true,
  "data": {
    "taskId": "pencil_20260603211804_6d110631ce",
    "status": "completed",
    "projectName": "Project A",
    "pageCount": 3,
    "modes": ["clean-editable", "visual-fidelity", "visual-ocr"],
    "boundarySource": "psdlike",
    "downloadUrl": "/api/pencil/projects/pencil_20260603211804_6d110631ce/download.zip",
    "warnings": [],
    "createdAt": "2026-06-03T13:18:04.000000+00:00",
    "updatedAt": "2026-06-03T13:18:09.000000+00:00"
  }
}
```

Failed example:

```json
{
  "success": true,
  "data": {
    "taskId": "pencil_20260603211804_6d110631ce",
    "status": "failed",
    "projectName": "Project A",
    "boundarySource": "psdlike",
    "error": "PSD-like runner not found: /opt/pencil-python-backend/services/psdlike-python/tools/run_one.py",
    "warnings": []
  }
}
```

Polling guidance:

```text
poll every 1s for small projects
poll every 2-3s for larger projects
stop after failed
download only after completed
```

## Manifest

```text
GET /api/pencil/projects/{taskId}/manifest
```

Only valid after completion.

If task is not completed:

```text
409 task is not completed
```

Success:

```json
{
  "success": true,
  "data": {
    "schema": "pencil.project_manifest.v1",
    "projectName": "Project A",
    "pageCount": 3,
    "modes": ["clean-editable", "visual-fidelity", "visual-ocr"],
    "boundarySource": "psdlike",
    "zip": "project.zip"
  }
}
```

The manifest is useful for audit and debugging. The caller does not need it before download unless it wants to show page/mode metadata.

## Download ZIP

```text
GET /api/pencil/projects/{taskId}/download.zip
```

Only valid after completion.

If task is not completed:

```text
409 task is not completed
```

Success:

```text
Content-Type: application/zip
Content-Disposition: attachment; filename="project.zip"
```

ZIP layout:

```text
manifest.json
clean-editable/design.pen
clean-editable/assets/visible/...
visual-fidelity/design.pen
visual-fidelity/assets/visible/...
visual-ocr/design.pen
visual-ocr/assets/visible/...
debug/report.md
debug/pages/...
```

## Modes

```text
clean-editable
```

普通 UI OCR 文本转为 editable TextLayer；媒体、商品、促销、包装内视觉文字保留 raster。

```text
visual-fidelity
```

纯视觉保真，不 overlay OCR TextLayer，不 knockout。

```text
visual-ocr
```

视觉保真基础上 overlay 安全 OCR TextLayer。

For customer delivery, prefer `mode=all` so the ZIP contains all three fallback choices.

## Assisted Slice Review

The assisted slice API is for cases where fully automatic ownership is not reliable enough. The server generates candidates, the user confirms or draws slices in a Canvas review page, and `manual_slices.v1.json` becomes the export truth source. M29, PSD-like, OCR, and foreground audit evidence only produce candidates; they do not decide final visible assets.

### Workspace

```text
GET /api/pencil/slice-projects/workspace
GET /api/pencil/slice-projects
```

`/workspace` returns a plain HTML project workbench. It can create projects, list historical projects, resume review, rename, clone, delete, and download exported packages. The JSON list endpoint scans local slice-project storage and derives summary data from `project.json`, `candidates.v1.json`, `manual_slices.v1.json`, and `review_state.v1.json`; no database is required.

Project summaries include:

```json
{
  "projectId": "slice_...",
  "projectName": "Assisted Slice Project",
  "status": "ready",
  "pageCount": 3,
  "candidateCount": 120,
  "selectedSliceCount": 18,
  "rejectedCandidateCount": 42,
  "completedPageCount": 2,
  "exported": false,
  "reviewUrl": "/api/pencil/slice-projects/slice_.../review",
  "thumbnailUrl": "/api/pencil/slice-projects/slice_.../source/page_0001"
}
```

Project management:

```text
PUT    /api/pencil/slice-projects/{projectId}        rename projectName
POST   /api/pencil/slice-projects/{projectId}/clone  clone project without exported output
DELETE /api/pencil/slice-projects/{projectId}        delete project directory
```

### Browser Upload Entry

```text
GET /api/pencil/slice-projects/new
```

Returns a plain HTML upload page. It lets a browser user select one or more images, set `projectName`, choose `boundarySource`, toggle `includeDebug`, create a slice project, and redirect to the returned review URL. This is the preferred manual entry point for local browser use.

### Create Slice Project

```text
POST /api/pencil/slice-projects
Content-Type: multipart/form-data
```

Fields:

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `files[]` or `files` | yes | none | 1..`PENCIL_BACKEND_MAX_FILES`; PNG/JPG/JPEG/WEBP only |
| `projectName` | no | `Assisted Slice Project` | Stored in project metadata and export manifest |
| `includeDebug` | no | `true` | Includes debug candidates/manual overlay in ZIP |
| `ocrProvider` | no | server `OCR_PROVIDER` | Used only by candidate evidence generation |
| `boundarySource` | no | server `PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE` | `psdlike`, `m29`, or `hybrid` candidate source |

Success:

```json
{
  "success": true,
  "data": {
    "projectId": "slice_20260604103000_abcdef1234",
    "status": "ready",
    "projectName": "Assisted Slice Project",
    "pageCount": 1,
    "pages": [
      {
        "pageId": "page_0001",
        "sourceImage": "pages/page_0001/source.png",
        "width": 665,
        "height": 1440
      }
    ],
    "boundarySource": "psdlike",
    "manualSlicesConfirmed": false,
    "selectedSliceCount": 0
  }
}
```

Creation writes:

```text
candidates.v1.json
manual_slices.v1.json
source images under pages/page_XXXX/source.png
```

The initial `manual_slices.v1.json` is empty so the review UI can load, but export is blocked until the caller saves manual slices with `PUT /manual-slices`.

### Review Page

```text
GET /api/pencil/slice-projects/{projectId}/review
```

Returns a static HTML Canvas workbench. It supports page switching, pan, zoom, fit-to-screen, 100% zoom, candidate filtering, candidate double-click selection, candidate box selection, bulk candidate add/reject/restore, manual box drawing, moving, 8-handle resizing, deleting, renaming, autosave, undo/redo, keyboard save, export preview, exporting, and downloading the resulting ZIPs.

The review page keeps two coordinate systems separate:

```text
screen coordinates: pan/zoom/view state only
source image coordinates: saved manual_slices bbox truth
```

Saved `manual_slices.v1.json` bboxes are always source-image coordinates, regardless of current zoom or pan.

Manual edits are autosaved with a short debounce. The status text reports:

```text
dirty
autosaving...
saved
save failed
```

Export waits for any pending autosave before it calls `POST /export`.

Default candidate display is tuned for slicing, not OCR proofreading:

```text
image/icon/group/shape/unknown visible
text hidden by default
selected slices visible
candidate labels visible
```

The page list shows page thumbnails, candidate counts, selected slice counts, and save state. The selected slice panel shows browser-rendered crop thumbnails from the source image so users can verify what will be exported without downloading the ZIP.

Candidate review state is saved separately from final manual slices:

```text
review_state.v1.json      workbench state: rejected candidates, filters, last active page
manual_slices.v1.json     delivery truth: selected slices only
```

Candidate tiers are UI-only filters:

```text
recommended
normal
noise
text
rejected
```

They are derived from candidate kind/source/confidence/reason and relative area. They do not change candidate generation and do not decide final export.

Workbench shortcuts:

```text
Delete / Backspace  delete active slice
Arrow keys          move active slice by 1 px
Shift + Arrow keys  move active slice by 10 px
Cmd/Ctrl + S        save immediately
Cmd/Ctrl + Z        undo manual_slices change
Cmd/Ctrl+Shift+Z    redo manual_slices change
Cmd/Ctrl + D        duplicate active slice
Alt/Option + Left   previous page
Alt/Option + Right  next page
Esc                 clear active drag/selection
```

### Candidates

```text
GET /api/pencil/slice-projects/{projectId}/candidates
```

Returns `pencil.slice_candidates.v1`:

```json
{
  "schema": "pencil.slice_candidates.v1",
  "projectId": "slice_...",
  "pages": [
    {
      "pageId": "page_0001",
      "sourceImage": "pages/page_0001/source.png",
      "width": 665,
      "height": 1440,
      "candidates": [
        {
          "id": "page_0001__candidate_0001",
          "kind": "image",
          "bbox": {"x": 40, "y": 1168, "width": 200, "height": 144},
          "source": "psdlike",
          "confidence": 0.72,
          "reason": "primitive_candidate",
          "selectedDefault": false
        }
      ]
    }
  ]
}
```

Candidate boxes are suggestions only. A caller should not export all candidates blindly.

### Manual Slices

```text
GET /api/pencil/slice-projects/{projectId}/manual-slices
PUT /api/pencil/slice-projects/{projectId}/manual-slices
```

`PUT` body must use `pencil.manual_slices.v1`:

```json
{
  "schema": "pencil.manual_slices.v1",
  "projectName": "My Project",
  "pages": [
    {
      "pageId": "page_0001",
      "slices": [
        {
          "id": "page_0001__slice_0001",
          "name": "hero_asset",
          "displayName": "Hero Asset",
          "kind": "image",
          "tags": ["hero"],
          "reviewState": "confirmed",
          "bbox": {"x": 40, "y": 1168, "width": 200, "height": 144},
          "selected": true,
          "exportMode": "rect",
          "source": "candidate_confirmed",
          "candidateIds": ["page_0001__candidate_0001"]
        }
      ]
    }
  ]
}
```

Validation rules:

```text
schema must be pencil.manual_slices.v1
every candidate page must be present exactly once
slice ids must be unique
exportMode must be rect
bbox must be non-zero and inside source image bounds
displayName, tags, and reviewState are optional and normalized when present
```

After a successful `PUT`, project status includes:

```json
{
  "manualSlicesConfirmed": true,
  "selectedSliceCount": 1
}
```

### Export Slice Project

```text
POST /api/pencil/slice-projects/{projectId}/export
```

Export is valid only after `PUT /manual-slices`. Calling export before saving manual slices returns:

```text
409 manual slices must be saved before export
```

Calling export after saving an empty or fully unselected manual slice document returns:

```text
409 no selected slices to export
```

The exporter crops selected slices from `pages/page_XXXX/source.png`, writes three `.pen` modes with slice assets placed back at exact source coordinates, and creates `selected-assets.zip`.

Export preview can be generated before the final ZIP:

```text
POST /api/pencil/slice-projects/{projectId}/export-preview
GET  /api/pencil/slice-projects/{projectId}/export-preview/contact-sheet.png
GET  /api/pencil/slice-projects/{projectId}/export-preview/index.html
```

The preview writes a contact sheet plus an HTML asset table under `output/export-preview/`. It requires at least one selected slice.

Success manifest:

```json
{
  "schema": "pencil.assisted_slice_project_manifest.v1",
  "projectName": "My Project",
  "pageCount": 1,
  "modes": ["clean-editable", "visual-fidelity", "visual-ocr"],
  "manualSlices": "manual_slices.v1.json",
  "selectedAssetsZip": "selected-assets.zip",
  "contactSheet": "resource-kit/contact-sheet.png",
  "selectedAssetCount": 1,
  "zip": "project.zip"
}
```

Downloaded ZIP:

```text
manifest.json
manual_slices.v1.json
selected-assets.zip
resource-kit/manifest.json
resource-kit/contact-sheet.png
clean-editable/design.pen
clean-editable/assets/visible/page_0001/...
visual-fidelity/design.pen
visual-fidelity/assets/visible/page_0001/...
visual-ocr/design.pen
visual-ocr/assets/visible/page_0001/...
debug/pages/page_0001/source.png
debug/pages/page_0001/candidates.v1.json
debug/pages/page_0001/manual_slices.v1.json
debug/pages/page_0001/overlay.png
```

After export, download endpoints are:

```text
GET /api/pencil/slice-projects/{projectId}/download.zip          Pencil/Figma project package
GET /api/pencil/slice-projects/{projectId}/selected-assets.zip   frontend asset package
```

## Boundary Sources

```text
psdlike
```

Default product path. Produces coarser, lower-fragment visual assets.

```text
m29
```

Legacy high-recall local executable path. Useful for debugging but can create more fragmented assets.

```text
hybrid
```

PSD-like primary boundary plus constrained M29 low-coverage fallback objects.

Caller rule:

```text
Omit boundarySource for normal product use.
Send boundarySource only for an explicit diagnostic or fallback run.
```

## Error Status Codes

| Status | Meaning | Caller Action |
| --- | --- | --- |
| `400` | Bad request: missing files, unsupported mode/type/boundary source, invalid columns | Show detail; let user fix input |
| `404` | Task, manifest, or ZIP not found | Stop polling; task id or server storage is wrong |
| `409` | Manifest/download requested before completion | Continue polling status |
| `413` | Too many files or file too large | Tell user limit from detail |
| `500` | Unexpected server failure | Show generic failure and keep task id for operator debug |

Task-level processing failures are represented as HTTP 200 status responses with `data.status = "failed"` and an `error` string.

## Minimal Browser Client Flow

```ts
async function createPencilProject(files: File[]) {
  const body = new FormData();
  for (const file of files) body.append("files[]", file);
  body.append("mode", "all");
  body.append("includeDebug", "true");

  const created = await fetch("/api/pencil/projects", {
    method: "POST",
    body,
  }).then(assertJson);

  const taskId = created.data.taskId;
  while (true) {
    await sleep(1000);
    const status = await fetch(`/api/pencil/projects/${taskId}`).then(assertJson);
    if (status.data.status === "failed") throw new Error(status.data.error || "Pencil export failed");
    if (status.data.status === "completed") return status.data.downloadUrl;
  }
}

async function assertJson(response: Response) {
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
```

## Smoke Contract

Deployment must pass:

```bash
cd services/pencil-python-backend
uv run python scripts/preflight.py
uv run python scripts/server_smoke.py \
  --base-url http://127.0.0.1:8100 \
  --image /absolute/path/to/sample.png \
  --out /tmp/pencil-http-smoke
```

Required output signals:

```text
health=ok
ready=ready
boundarySource=psdlike
status=completed
badRefs=0
missingRefs=0
serverSmoke=ok
```

## HTTP Client CLI

For non-frontend automation, use the repository caller CLI instead of hand-writing curl:

```bash
cd services/pencil-python-backend
uv run python scripts/upload_project.py \
  --base-url http://127.0.0.1:8100 \
  --input /absolute/path/to/screens \
  --out /Volumes/WorkDrive/pencil-exports/http-project \
  --project-name "HTTP Project" \
  --mode all
```

By default it omits `boundarySource`, polls until completion, downloads `project.zip`, writes `manifest.json`, and verifies `.pen` visible image refs.

## Assisted Slice Workspace Acceptance

Use this for the synchronous assisted slice workspace path:

```bash
cd services/pencil-python-backend
make slice-acceptance \
  BASE_URL=http://127.0.0.1:8100 \
  IMAGE=/absolute/path/to/image-or-dir \
  OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance
```

The script verifies:

```text
projectCreated=true
pageCount>=1
candidateCount>0
manualSliceSaved=true
reviewStateSaved=true
exportPreviewGenerated=true
projectZipExists=true
selectedAssetsZipExists=true
selectedAssetCount == selected PNG count
badRefs=0
missingRefs=0
```

It writes `acceptance_report.md` and `acceptance_report.json` under `OUT`.
