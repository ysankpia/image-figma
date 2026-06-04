# API Contracts

Current product runtime is Pencil assisted slice, documented in
[../reference/pencil-python-backend-api.md](../reference/pencil-python-backend-api.md).

This file records historical/deferred Draft Preview contracts served by the Go
backend. Use it only when explicitly working on `/api/draft-preview`.

## Base URL

Development default:

```text
http://localhost:8000/api
```

## Response Shape

Success:

```json
{
  "success": true,
  "data": {}
}
```

Failure:

```json
{
  "success": false,
  "error": {
    "code": "UPLOAD_FAILED",
    "message": "PNG upload failed.",
    "detail": "Internal debug detail",
    "stage": "draft_upload",
    "taskId": "task_001"
  }
}
```

## Required Draft Endpoints

### `GET /api/health`

Returns backend liveness:

```text
status
version
time
```

Draft server should report a Draft-specific version string.

### `POST /api/draft-preview`

Uploads one PNG and starts a Draft task.

Request:

```text
multipart/form-data
file: image/png
```

Validation:

- MIME must be `image/png`.
- PNG signature must be valid.
- IHDR dimensions must be readable.
- File size must be <= `DRAFT_SERVER_MAX_UPLOAD_BYTES`.

Immediate success response:

```json
{
  "success": true,
  "data": {
    "taskId": "task_abc",
    "status": "queued",
    "stage": "draft_queued",
    "progress": 1,
    "file": {
      "filename": "upload.png",
      "mimeType": "image/png",
      "size": 1234,
      "width": 390,
      "height": 844
    }
  }
}
```

### `GET /api/draft-preview/{taskId}`

Returns task status:

```json
{
  "success": true,
  "data": {
    "taskId": "task_abc",
    "status": "running",
    "stage": "draft_assemble",
    "progress": 60,
    "message": "Assembling editable layers.",
    "warnings": [
      {
        "code": "DRAFT_VISION_FALLBACK",
        "message": "missing detector API key: set VISION_API_KEY",
        "stage": "vision_detector",
        "artifact": "vision/vision_detector_fallback.v1.json"
      }
    ]
  }
}
```

Status values:

```text
queued
running
completed
failed
```

Stage values should be Draft-specific:

```text
draft_queued
ocr
m29_physical_evidence
vision_detector
vision_review
draft_assemble
draft_assets
draft_validate
draft_export
draft_completed
draft_failed
```

### `GET /api/draft-preview/{taskId}/dsl`

Returns `draft_runtime.dsl.v1.json` only after task completion.

If the task is not completed, return `DSL_NOT_READY`.

The DSL must be derived from `editable_layer_graph.v1.json`; exporter code must not make ownership decisions.

### `GET /api/draft-preview/{taskId}/assets/{assetId}.png`

Returns a local raster asset referenced by the Draft DSL.

Completed tasks must not expose visible raster layers with unresolved asset IDs.

### `GET /api/draft-preview/{taskId}/artifacts`

Optional development endpoint returning artifact paths and summary metadata. It is not required by the renderer.

Typical artifact keys:

```text
m29PhysicalEvidence
evidenceTokens
visionCandidates
visionReport
visionOverlay
visionRawResponses
visionFallback
editableLayerGraph
validationReport
assetManifest
runtimeDsl
```

Vision artifact keys are optional. If optional vision fails, `visionFallback` and a task warning must be returned; the completed Draft task should still expose `editableLayerGraph`, `runtimeDsl`, `assetManifest`, and `validationReport`.

## Removed Product Endpoints

The following endpoints are not product runtime contracts on this branch:

```text
POST /api/codia-preview
GET /api/codia-preview/{taskId}
GET /api/codia-preview/{taskId}/dsl
POST /api/upload-preview
GET /api/tasks/{taskId}/dsl
```

`/api/codia-preview` has been removed from the Go product server. Python `/api/upload-preview` may remain in historical/reference code, but new product work must target `/api/draft-preview`.

## Contract Ownership

Backend and Figma plugin jointly own this contract. Any endpoint, response shape, task state, stage, or error-code change must update this document and the active plan.
