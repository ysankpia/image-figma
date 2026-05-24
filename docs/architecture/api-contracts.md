# API Contracts

API v0.1 serves the current single-image preview path:

```text
PNG upload
-> OCR
-> raw M29 / M29.2 / M29.3 / M29.4 / M29.5
-> M29 Direct compare variant
-> legacy M29.0.x bridge
-> M30 DSL v0.1
-> Figma Renderer
```

M31/M37/M38/M39/M39.1 downstream diagnostic endpoints have been removed from current runtime.

## Contract Ownership

Backend and Figma plugin jointly own this contract. Any endpoint, response shape, task state, or error-code change must update this document and the relevant implementation plan.

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
    "stage": "upload_m30_preview",
    "taskId": "task_001"
  }
}
```

## Required Endpoints

### `GET /api/health`

Returns backend liveness:

```text
status
version
time
```

### `POST /api/upload-m30-preview`

Plugin default upload endpoint.

Request:

```text
multipart/form-data
file: image/png
```

Validation:

- MIME must be `image/png`.
- PNG signature must be valid.
- IHDR dimensions must be readable.
- File size must be <= `MAX_UPLOAD_BYTES`.

Immediate success response:

```json
{
  "success": true,
  "data": {
    "taskId": "task_abc",
    "status": "processing",
    "stage": "m30_queued",
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

The endpoint creates a task and runs the current M29/M30 pipeline in a background task. It does not run the removed pre-M29 chain or removed downstream M31-M39 stages.

On `experiment/m29-direct-replay`, the same task also writes an experimental M29 Direct Replay variant. This variant is not saved in `dsl_results` and does not replace the mainline DSL endpoint.

### `GET /api/tasks/{taskId}`

Returns task status:

```json
{
  "success": true,
  "data": {
    "taskId": "task_abc",
    "status": "processing",
    "stage": "m29_0_4",
    "progress": 74,
    "message": "Building visual object candidates."
  }
}
```

Status values:

```text
processing
completed
failed
```

### `GET /api/tasks/{taskId}/dsl`

Returns the generated DSL only after the task is completed.

Current preview DSL file:

```text
storage/m30_1_uploads/{taskId}/m30/m30_materialized_dsl.json
```

The DSL must:

- preserve fallback.
- include M30 materialization metadata.
- use visible `text`, `shape`, and `image` nodes only.
- never emit visible mixed/future/audit-only evidence.
- never emit DSL `icon` type from the M30 upload path.

If the task is not completed, the endpoint returns `DSL_NOT_READY`.

### `GET /api/tasks/{taskId}/m29-direct-dsl`

Returns the experimental M29 Direct Replay variant only after the task is completed.

Response data:

```json
{
  "dsl": {},
  "report": {
    "summary": {},
    "warnings": [],
    "outputReport": "/abs/path/m29_direct_replay_report.json",
    "stageTimings": {}
  }
}
```

Variant files:

```text
storage/m30_1_uploads/{taskId}/m29_direct/m29_direct_replay_dsl.json
storage/m30_1_uploads/{taskId}/m29_direct/m29_direct_replay_report.json
storage/m30_1_uploads/{taskId}/m29_2/source_ui_physical_graph.json
storage/m30_1_uploads/{taskId}/m29_5/replay_plan.json
```

If the task is not completed, the endpoint returns `DSL_NOT_READY`. If the variant does not exist, or if `m29_direct_asset_publish` did not complete, it returns `M29_DIRECT_DSL_NOT_FOUND`.

This endpoint is for Figma compare mode and route experiments only. It does not change `/api/tasks/{taskId}/dsl`.

### `GET /api/tasks/{taskId}/m30-materialization`

Returns M30 materialization diagnostics:

```text
summary
warnings
skippedItems
textEditabilityDecisions
preservedGraphicTextItems
reviewTextItems
debugPreviewPath
outputDsl
stageTimings
```

This endpoint is read-only and is not required by the Figma renderer.

### `GET /api/assets/{assetId}`

Returns the latest asset metadata for a stored asset ID:

```text
assetId
taskId
role
url
mimeType
```

### Static Files

```text
GET /files/uploads/*
GET /files/assets/*
```

M30 and M29 Direct image assets referenced by the renderer must be fetchable through `/files/assets/...`.

## Removed Endpoints

These routes are historical and must not be treated as current runtime contracts:

```text
POST /api/upload
GET /api/tasks/{taskId}/m31-reconstruction
GET /api/tasks/{taskId}/m39-boundary-classification
GET /api/tasks/{taskId}/m39-1-unit-structure-readiness
old M8-M28 debug endpoints
```
