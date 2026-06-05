# Historical Python Upload Preview Backend

This directory is retained as historical/research code for the old Python `/api/upload-preview` pipeline. It is not the current product delivery backend on `main`.

Current product work belongs in:

```text
services/pencil-python-backend/
```

Current code ownership and legacy classification are documented in:

```text
docs/engineering/current-code-map.md
docs/engineering/legacy-code-inventory.md
```

Do not use this directory as the starting point for assisted slice workspace, Pencil `.pen` export, `project.zip`, or `selected-assets.zip` work.

## Historical Runtime

The historical preview runtime in this directory was M29 plan-driven:

```text
Figma plugin
-> POST /api/upload-preview
-> OCR
-> raw M29 primitive graph
-> M29.2 source ownership
-> M29.3 relation graph
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> M29 plan-driven materialized DSL
-> GET /api/tasks/{taskId}/dsl
-> Renderer writes Figma nodes
```

`/api/upload-preview` is the historical upload-preview endpoint. It is not the current product endpoint on `main`.

The frozen pre-M29 upload chain, M29 Direct compare product endpoint, legacy M30 materialization product path, M31-M39/M39.1 downstream experiments, and ONNX proposer are not active backend runtime.

## Run

```bash
uv sync
UPLOAD_PREVIEW_PROFILE=production uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`UPLOAD_PREVIEW_PROFILE` controls artifact retention only. It does not change ownership, replay decisions, DSL schema, or Renderer behavior.

## Test

```bash
uv run pytest -q
```

Focused current-chain checks:

```bash
uv run pytest \
  tests/test_visual_primitive_graph.py \
  tests/test_source_ui_physical_graph.py \
  tests/test_region_relation_kernel.py \
  tests/test_region_relation_graph_report.py \
  tests/test_stable_design_cluster.py \
  tests/test_m29_replay_plan.py \
  tests/test_m29_plan_materializer.py \
  tests/test_upload_preview_pipeline.py \
  tests/test_routes_tasks.py \
  tests/test_config_env.py \
  tests/test_png_tools.py \
  tests/test_upload_flow.py \
  -q
```

## Historical API

```text
GET  /api/health
POST /api/upload-preview
GET  /api/tasks/{taskId}
GET  /api/tasks/{taskId}/dsl
GET  /api/tasks/{taskId}/materialization
GET  /api/assets/{assetId}
GET  /files/uploads/*
GET  /files/assets/*
```

Removed product routes:

```text
POST /api/upload
GET /api/tasks/{taskId}/m29-direct-dsl
GET /api/tasks/{taskId}/m30-materialization
GET /api/tasks/{taskId}/m31-reconstruction
GET /api/tasks/{taskId}/m39-boundary-classification
GET /api/tasks/{taskId}/m39-1-unit-structure-readiness
old M8-M28 debug endpoints
```

On success, the task reaches:

```text
status = completed
stage = m29_completed
progress = 100
```

`GET /api/tasks/{taskId}/dsl` returns:

```text
storage/upload_previews/{taskId}/materialized_design/design.dsl.json
```

`GET /api/tasks/{taskId}/materialization` returns the materialization report summary, warnings, skipped items, replayed nodes, output paths, and `stage_timings.json`.

## Historical Pipeline

The upload preview pipeline runs:

```text
OCR
-> raw M29 visual primitive graph
-> M29.2 source-level UI physical graph
-> M29.3 relation graph report
-> M29.4 stable design cluster report
-> M29.5 replay plan
-> M29 plan-driven materialization
-> publish M29 image assets under /files/assets/{taskId}/m29/
```

It deliberately does not run:

```text
M29 Direct compare replay
M29.0.x legacy bridge
M30 legacy materializer
old pre-M29 diagnostic stages
removed M31-M39 downstream stages
fallback masking experiments
Auto Layout
Figma Components
SVG/vectorization
icon recovery
```

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

In the preview pipeline, OCR is required evidence. If the configured OCR provider fails, the task is marked `failed`; the backend does not create a fake completed DSL.

## M29 Preview Profile

```bash
UPLOAD_PREVIEW_PROFILE=production   # default plugin preview runtime
UPLOAD_PREVIEW_PROFILE=development  # full raw M29 diagnostics for local debugging
```

`production` keeps OCR JSON, structured M29/M29.2/M29.3/M29.4/M29.5 JSON, M29 materialized DSL/report, published renderer assets, and `stage_timings.json`. It skips raw M29 overlays and preview sheets where possible.

`development` preserves raw M29 diagnostic output such as overlays and preview sheet. The profile affects artifacts only; it does not change ownership, replay decisions, DSL schema, or Renderer behavior.

## M29 Contract Chain

M29 source truth is protected by:

```text
raw M29
-> M29.2 source ownership
-> M29.3 region relation
-> M29.4 weak cluster
-> M29.5 replay plan
-> M29 plan-driven materializer
```

M29.2 classifies source pixel ownership into editable text, preserved raster text, media, raster icons, stable UI shapes, and diagnostic-only objects. M29.5 decides visible replay actions, deduplication, ordering, node budget, fallback cleanup, and copied raster/media asset cleanup authorization. M29.4 remains weak structural evidence; it does not grant component, Auto Layout, or Figma Component/Instance permission.

## Materialization

`backend/app/m29_plan_materializer.py` is the formal DSL producer. It:

- requires an M29.5 replay plan.
- starts from deterministic fallback DSL.
- samples root/page background from source PNG instead of using a fixed light background.
- appends only plan-approved visible actions.
- writes `m29_text`, `m29_shape`, `m29_image`, and `m29_symbol` roles.
- executes fallback erasure only when the plan item has a `fallback` cleanup target.
- executes copied image asset text cleanup only when the plan item has a `copied_image_asset` cleanup target.

It does not:

```text
run a separate text editability classifier
invent new bbox
derive support backgrounds from text padding
special-case dark mode, a screenshot, a color, a language, or a business category
promote M29.4 clusters into components
```

## Storage

Runtime storage lives under `backend/storage/` by default and is not committed.

Historical runtime directories:

```text
storage/uploads/
storage/assets/
storage/dsl/
storage/ocr/
storage/logs/
storage/upload_previews/
```

Each upload task may include:

```text
storage/upload_previews/{taskId}/ocr/
storage/upload_previews/{taskId}/m29/
storage/upload_previews/{taskId}/m29_2/
storage/upload_previews/{taskId}/m29_3/
storage/upload_previews/{taskId}/m29_4/
storage/upload_previews/{taskId}/m29_5/
storage/upload_previews/{taskId}/materialized_design/
storage/upload_previews/{taskId}/stage_timings.json
```

Renderer-fetchable image assets are published to:

```text
storage/assets/{taskId}/m29/
http://localhost:8000/files/assets/{taskId}/m29/...
```

## Removed Legacy Surface

History remains in git, old ADRs, completed plans, and `docs/reference/legacy/`. Do not restore these as product paths without a new plan and tests:

```text
POST /api/upload
old M8-M28 task debug endpoints
M29 Direct compare endpoint
M29.0.x legacy bridge
M30 materializer product path
M31 reconstruction diagnostics
M37 hierarchy readiness
M38 hierarchy materialization
M39 content/chrome classification
M39.1 unit structure readiness
ONNX proposer
legacy app modules
legacy smoke scripts
legacy module tests
```
