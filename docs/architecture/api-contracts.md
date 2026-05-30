# API Contracts

API v0.1 serves the current single-image M29 plan-driven preview path:

```text
PNG upload
-> OCR
-> raw M29 / M29.2 / M29.3 / M29.4 / M29.5
-> M29 plan-driven DSL v0.1
-> Figma Renderer
```

`POST /api/upload-preview` is the product upload endpoint. Runtime semantics are M29 mainline.

Codia Beta has a separate Go server contract under `/api/codia-preview`. It returns DSL v0.2 Codia Runtime data for `renderCodiaRuntimeDesign`. It is not the formal product DSL endpoint and must not change `/api/tasks/{taskId}/dsl`.

M29 Direct compare, legacy M30 materialization diagnostics, M31/M37/M38/M39/M39.1 downstream diagnostics, and old M8-M28 debug endpoints have been removed from current runtime.

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
    "stage": "upload_preview",
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

Both Python FastAPI and Go `codiaserver` expose this path. The Go server reports `version=codia-server-v0.1`.

### `POST /api/upload-preview`

Plugin default upload endpoint. The task it creates runs the M29 plan-driven pipeline.

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
    "stage": "m29_queued",
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

The endpoint creates a task and runs the current M29 pipeline in a background task. It does not run the removed pre-M29 chain, removed M29 Direct compare path, removed legacy M30 product materializer, or removed downstream M31-M39 stages.

### `GET /api/tasks/{taskId}`

Returns task status:

```json
{
  "success": true,
  "data": {
    "taskId": "task_abc",
    "status": "processing",
    "stage": "m29_5_replay_plan",
    "progress": 25,
    "message": "Building M29.5 replay quality plan."
  }
}
```

Status values:

```text
processing
completed
failed
```

Current stage values:

```text
m29_queued
ocr
m29
m29_2_source_ui_physical_graph
m29_3_relation_graph_report
m29_4_stable_design_cluster
m29_5_replay_plan
m29_materialization
m29_asset_publish
m29_completed
```

### `GET /api/tasks/{taskId}/dsl`

Returns the generated DSL only after the task is completed.

Current preview DSL file:

```text
storage/upload_previews/{taskId}/materialized_design/design.dsl.json
```

The DSL must:

- preserve fallback and hidden original reference.
- include M29 plan-driven materialization metadata.
- use visible `text`, `shape`, and `image` nodes only.
- use M29 roles such as `m29_text`, `m29_shape`, `m29_image`, and `m29_symbol`.
- never emit visible mixed/future/audit-only evidence.
- never infer Auto Layout or Figma Component/Instance.

If the task is not completed, the endpoint returns `DSL_NOT_READY`.

### `GET /api/tasks/{taskId}/materialization`

Returns M29 plan-driven materialization diagnostics:

```text
summary
warnings
skippedItems
replayedNodes
outputDsl
outputReport
stageTimings
```

This endpoint is read-only and is not required by the Figma renderer.

The report answers:

```text
which M29.5 plan items were replayed
which items were skipped
how many text/shape/image/icon nodes were created
whether fallback cleanup executed
whether copied raster/media asset cleanup executed
which source objects and plan items authorized cleanup
```

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

M29 materialized image assets referenced by the renderer must be fetchable through `/files/assets/...`.

## Codia Beta Go Server Endpoints

These endpoints are served by `services/backend-go/cmd/codiaserver`.

### `POST /api/codia-preview`

Plugin Beta upload endpoint. The task it creates runs the Go Codia compiler and writes DSL v0.2.

Request:

```text
multipart/form-data
file: image/png
```

Validation:

- PNG signature must be valid.
- IHDR dimensions must be readable.
- File size must be <= `CODIA_SERVER_MAX_UPLOAD_BYTES`.

Immediate success response:

```json
{
  "success": true,
  "data": {
    "taskId": "task_abc",
    "status": "processing",
    "stage": "codia_queued",
    "progress": 1,
    "file": {
      "filename": "upload.png",
      "mimeType": "image/png",
      "size": 1234
    }
  }
}
```

### `GET /api/codia-preview/{taskId}`

Returns Go Codia task status:

```json
{
  "success": true,
  "data": {
    "taskId": "task_abc",
    "status": "processing",
    "stage": "codia_compile",
    "progress": 40,
    "message": "Running Go Codia compiler."
  }
}
```

Status values:

```text
processing
completed
failed
```

Current stage values:

```text
codia_queued
codia_detector
codia_compile
codia_completed
```

### `GET /api/codia-preview/{taskId}/dsl`

Returns the generated DSL v0.2 only after the task is completed.

Current preview DSL file:

```text
storage/codia_server/codia_previews/{taskId}/compile/codia_runtime.dsl.v0_2.json
```

Image assets referenced by DSL v0.2 are generated from source PNG `sourceBBox` crops and saved under:

```text
storage/codia_server/codia_previews/{taskId}/compile/assets/*.png
```

The response shape is:

```json
{
  "success": true,
  "data": {
    "dsl": {
      "version": "0.2",
      "kind": "codia_runtime"
    }
  }
}
```

If the task is not completed, the endpoint returns `DSL_NOT_READY`.

### `GET /api/codia-preview/{taskId}/assets/{assetId}.png`

Returns one local image crop generated for a Codia Runtime `type="image"` node.

The DSL asset URL is relative to the task endpoint:

```json
{
  "assetId": "asset_leaf_0007",
  "url": "assets/asset_leaf_0007.png",
  "format": "png",
  "storage": "local"
}
```

The plugin passes `assetBaseUrl=/api/codia-preview/{taskId}` to the Codia Runtime renderer so that the image can be loaded from:

```text
/api/codia-preview/{taskId}/assets/asset_leaf_0007.png
```

### `GET /api/codia-preview/{taskId}/artifacts`

Returns task artifact paths for local debugging:

```text
taskId
status
stage
outputDir
artifacts
```

This endpoint is read-only and not required by the plugin renderer.

## Removed Endpoints

These routes are historical and must not be treated as current runtime contracts:

```text
POST /api/upload
GET /api/tasks/{taskId}/m29-direct-dsl
GET /api/tasks/{taskId}/m30-materialization
GET /api/tasks/{taskId}/m31-reconstruction
GET /api/tasks/{taskId}/m39-boundary-classification
GET /api/tasks/{taskId}/m39-1-unit-structure-readiness
old M8-M28 debug endpoints
```
