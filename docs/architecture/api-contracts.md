# API Contracts

API v0.1 serves the current single-image preview path:

```text
PNG upload
-> OCR + M29 + M31 diagnostics + M30
-> DSL v0.1
-> Figma Renderer
```

## Contract Ownership

The backend and Figma plugin jointly own this contract. Any path, response shape, task state, or error-code change must update this document and the relevant implementation plan.

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

The endpoint creates a task and runs OCR + M29 + M30 in a background task. It does not run the removed pre-M29 upload chain.
M31 reconstruction diagnostics run after M29 when `M31_UPLOAD_DIAGNOSTICS_ENABLED=true`; they do not change the DSL output.

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

Status values currently used:

```text
processing
completed
failed
```

### `GET /api/tasks/{taskId}/dsl`

Returns the generated DSL only after the task is completed.

For current preview tasks, the DSL file is:

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

### `GET /api/tasks/{taskId}/m30-materialization`

Returns M30 materialization diagnostics:

```text
summary
warnings
skippedItems
debugPreviewPath
outputDsl
stageTimings
```

This endpoint is read-only and is not required by the Figma renderer.

### `GET /api/tasks/{taskId}/m31-reconstruction`

Returns M31 reconstruction diagnostics generated from source PNG, OCR JSON, and M29 `nodes.json`.

Response data:

```json
{
  "taskId": "task_abc",
  "status": "completed",
  "stage": "m30_completed",
  "summary": {
    "primitiveRefCount": 12,
    "unitCount": 5,
    "reviewBucketCount": 0,
    "primitiveOwnershipRate": 1.0,
    "orphanPrimitiveCount": 0,
    "rootLeafPrimitiveCount": 0,
    "unitFallbackCoverage": 1.0,
    "createdDetectionBBoxCount": 0,
    "permissionViolationCount": 0,
    "forbiddenHitCount": 0
  },
  "warnings": [],
  "reviewBuckets": [],
  "unitSummaries": [],
  "outputTree": "/abs/path/m31_reconstruction_tree.json",
  "debugOverlayPath": null,
  "stageTimings": {}
}
```

This endpoint is read-only, returns report-level data only, and is not required by the Figma renderer. It does not return the full tree JSON.

If the task exists but M31 diagnostics are disabled or failed in optional mode, the endpoint returns `M31_RECONSTRUCTION_NOT_FOUND`.

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

M30 image assets referenced by the renderer must be fetchable through:

```text
/files/assets/{taskId}/m30/...
```

## Removed Endpoints

The following are not part of the active API contract:

```text
POST /api/upload
GET /api/tasks/{taskId}/primitives
GET /api/tasks/{taskId}/ocr
GET /api/tasks/{taskId}/dsl-patch
GET /api/tasks/{taskId}/text-replacements
GET /api/tasks/{taskId}/text-bindings
GET /api/tasks/{taskId}/component-structures
GET /api/tasks/{taskId}/component-annotations
GET /api/tasks/{taskId}/layer-separation-candidates
GET /api/tasks/{taskId}/asset-slice-candidates
GET /api/tasks/{taskId}/icon-candidates
GET /api/tasks/{taskId}/icon-coverage-audit
GET /api/tasks/{taskId}/icon-gap-candidates
GET /api/tasks/{taskId}/icon-placement-plan
GET /api/tasks/{taskId}/icon-visible-fallback
GET /api/tasks/{taskId}/icon-business-candidates
GET /api/tasks/{taskId}/perception-benchmark
GET /api/tasks/{taskId}/sam-visual-candidates
```

They were removed in M30.2.2. Historical behavior is preserved only through git history, ADRs, and archived reference docs.
