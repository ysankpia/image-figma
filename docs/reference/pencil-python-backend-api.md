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
