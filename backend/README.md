# Image-to-Figma Backend

FastAPI backend for the current Image-to-Figma preview pipeline.

The product runtime is now:

```text
Figma plugin
-> POST /api/upload-m30-preview
-> OCR + M29 evidence pipeline
-> M31 reconstruction diagnostics
-> M30 materialized DSL
-> GET /api/tasks/{taskId}/dsl
-> Renderer writes Figma nodes
```

The frozen pre-M29 upload chain has been removed from runtime source. `POST /api/upload` and the old task debug endpoints are not product contracts.

M31 is attached as a diagnostic side path after M29. It builds a reconstruction UI tree from source PNG, OCR JSON, and M29 `nodes.json`; it does not change M30 DSL or Figma output.

## Run

```bash
uv sync
M30_PREVIEW_PROFILE=production uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Test

```bash
uv run pytest -q
```

Focused current-chain checks:

```bash
uv run pytest \
  tests/test_m30_upload_pipeline.py \
  tests/test_evidence_grounded_dsl_materialization.py \
  tests/test_upload_flow.py \
  tests/test_config_env.py \
  tests/test_assets.py \
  tests/test_baidu_ocr.py -q
```

## Current API

```text
GET  /api/health
POST /api/upload-m30-preview
GET  /api/tasks/{taskId}
GET  /api/tasks/{taskId}/dsl
GET  /api/tasks/{taskId}/m30-materialization
GET  /api/tasks/{taskId}/m31-reconstruction
GET  /api/assets/{assetId}
GET  /files/uploads/*
GET  /files/assets/*
```

`/api/upload-m30-preview` validates a PNG, stores it at `storage/uploads/{taskId}/original.png`, creates a `processing` task, and runs the M30 preview pipeline in a FastAPI background task. The initial response keeps the existing upload result shape with `taskId`, `status`, `stage`, `progress`, and file metadata.

On success, the task reaches:

```text
status = completed
stage = m30_completed
progress = 100
```

`GET /api/tasks/{taskId}/dsl` then returns `storage/m30_1_uploads/{taskId}/m30/m30_materialized_dsl.json`.

`GET /api/tasks/{taskId}/m30-materialization` returns the M30 report summary, warnings, skipped items, output DSL path, optional debug preview path, and `stage_timings.json`.

`GET /api/tasks/{taskId}/m31-reconstruction` returns M31 reconstruction summary metrics, warnings, review buckets, unit summaries, the full tree path, optional debug overlay path, and `stage_timings.json`. It does not return the full tree JSON.

## Current Pipeline

The upload preview pipeline runs:

```text
OCR
-> M29 visual primitive graph
-> M31 reconstruction diagnostics
-> M29.1 symbol fragment grouping
-> M29.0.2 text-masked media audit
-> M29.0.3 visual evidence normalization with lineage
-> M29.0.7 text/visual ownership gate
-> M29.0.4 visual object candidate audit with ownership routing
-> M29.0.5 text-aware visual object refinement
-> M30 evidence-grounded DSL materialization
-> M30.2 conservative text cover
-> publish M30 image assets under /files/assets/{taskId}/m30/
```

It deliberately does not run old pre-M29 diagnostic stages, mixed/residual acceptance audits, fallback masking, Auto Layout, Figma Components, SVG/vectorization, or icon recovery.

## OCR

Default OCR provider:

```bash
OCR_PROVIDER=fake
```

Optional Baidu PP-OCRv5 async OCR:

```bash
OCR_PROVIDER=baidu_ppocrv5 \
BAIDU_PADDLE_OCR_TOKEN=... \
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In the M30 preview pipeline, OCR is required evidence. If the configured OCR provider fails, the task is marked `failed`; the backend does not create a fake completed M30 DSL.

## M30 Preview Profile

```bash
M30_PREVIEW_PROFILE=production   # default plugin preview runtime
M30_PREVIEW_PROFILE=development  # full diagnostics for local debugging
```

`production` keeps OCR JSON, structured M29/M30 JSON, M29.0.5 formal visual assets needed by M30, published renderer assets, M30 DSL/report, and `stage_timings.json`. It skips overlays, preview sheets, review/contact sheets, and M30 preview PNGs.

`development` preserves full diagnostic output. Single-stage M29/M30 scripts still default to development-style output through their own function defaults.

## M31 Upload Diagnostics

```bash
M31_UPLOAD_DIAGNOSTICS_ENABLED=true   # default
M31_UPLOAD_DIAGNOSTICS_STRICT=false   # default
```

When enabled, `/api/upload-m30-preview` writes:

```text
storage/m30_1_uploads/{taskId}/m31/m31_reconstruction_tree.json
storage/m30_1_uploads/{taskId}/m31/m31_reconstruction_tree_report.json
storage/m30_1_uploads/{taskId}/m31/m31_unit_fallback_assets/
```

`M30_PREVIEW_PROFILE=production` skips the M31 overlay. `M30_PREVIEW_PROFILE=development` also writes `m31_reconstruction_tree_overlay.png`.

M31 failures are optional by default: they write failed stage timing and an error log, then the pipeline continues to M30. With `M31_UPLOAD_DIAGNOSTICS_STRICT=true`, M31 failure marks the task failed at `stage=m31_reconstruction`.

## M30 Materialization

M30 is the bridge from trusted M29.0.5 evidence into existing DSL v0.1. It consumes:

```text
textMembers
shapeCandidates
safe visualAssets
```

It does not consume mixed/future/audit-only evidence as visible DSL children. Those references may appear only in reports or DSL meta.

Safe visual assets are emitted as DSL `image` nodes, not `icon` nodes, because the current renderer does not implement an `icon` DSL type for this path.

M30.2 adds conservative `m30_text_cover` shape nodes only when source PNG background sampling is stable and overlap risk is low. It does not hide fallback, mask fallback regions, or do inpainting.

## M31 Reconstruction UI Tree

M31 starts the next abstraction layer:

```text
source PNG + OCR JSON + M29 nodes.json
-> reconstruction UI tree
-> reconstruction units with fallback crops
-> ownership/report/overlay
```

Run it manually:

```bash
uv run python scripts/run_m31_reconstruction_ui_tree.py \
  --source-image storage/uploads/{taskId}/original.png \
  --ocr-json storage/m30_1_uploads/{taskId}/ocr/ocr.json \
  --m29-nodes-json storage/m30_1_uploads/{taskId}/m29/nodes.json \
  --out storage/m31_runs/{taskId} \
  --profile development
```

M31.1 is a runtime diagnostic API, not a Renderer input. It deliberately does not consume M29.0.2/M29.0.3/M29.0.4/M29.0.5 or M30 DSL as structural truth. Those stages remain in the current product runtime until later M32-M34 stages replace their responsibility.

## Storage

Runtime storage lives under `backend/storage/` by default and is not committed.

Current runtime directories:

```text
storage/uploads/
storage/assets/
storage/dsl/
storage/ocr/
storage/logs/
storage/m30_1_uploads/
storage/m31_runs/
```

Each upload task may now include:

```text
storage/m30_1_uploads/{taskId}/m31/
```

M30 preview tasks also publish renderer-fetchable image assets to:

```text
storage/assets/{taskId}/m30/
http://localhost:8000/files/assets/{taskId}/m30/...
```

## Removed Legacy Surface

M30.2.2 permanently removed the frozen pre-M29 backend chain from active source:

```text
POST /api/upload
old M8-M28 task debug endpoints
LEGACY_PRE_M29_UPLOAD_ENABLED
legacy app modules
legacy smoke scripts
legacy module tests
```

History remains in git, old ADRs, and `docs/reference/legacy/`. The active backend no longer provides an environment flag to revive the old path.
