# Image-to-Figma Backend

FastAPI backend for the current Image-to-Figma preview pipeline.

Current product runtime:

```text
Figma plugin
-> POST /api/upload-m30-preview
-> OCR
-> raw M29 primitive graph
-> M29.2 source ownership
-> M29.3 relation graph
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> M29 Direct Replay compare variant
-> legacy M29.0.x bridge
-> M30 materialized DSL
-> GET /api/tasks/{taskId}/dsl
-> Renderer writes Figma nodes
```

The frozen pre-M29 upload chain has been removed from runtime source. M31-M39/M39.1 downstream experiments and ONNX proposer have also been pruned from backend runtime. Their old ADRs and completed plans are historical records, not active API or pipeline facts.

On `experiment/m29-direct-replay`, each upload task also writes an experimental M29 Direct variant for side-by-side Figma comparison. It uses the same OCR and raw M29 evidence, runs M29.2-M29.5, writes `m29_direct/m29_direct_replay_dsl.json`, publishes assets under `/files/assets/{taskId}/m29_direct/`, and is available through `GET /api/tasks/{taskId}/m29-direct-dsl`. It does not replace the mainline `/dsl` result. M29 Direct failures are non-blocking; the mainline task can still complete and the variant endpoint then returns `M29_DIRECT_DSL_NOT_FOUND` if the direct variant is unavailable.

M30 remains the current default `/dsl` bridge. It materializes safe text, shapes, images, and composite media into DSL layers, then deduplicates raster pixels that would otherwise be drawn twice. Editable text remains a top layer; if it sits inside a copied media asset, M30.7 erases that text bbox from the copied asset only. M29.0.5 source assets are never modified.

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
  tests/test_visual_primitive_graph.py \
  tests/test_source_ui_physical_graph.py \
  tests/test_region_relation_kernel.py \
  tests/test_region_relation_graph_report.py \
  tests/test_stable_design_cluster.py \
  tests/test_m29_replay_plan.py \
  tests/test_m29_direct_replay.py \
  tests/test_evidence_grounded_dsl_materialization.py \
  tests/test_m30_upload_pipeline.py \
  tests/test_routes_tasks.py \
  tests/test_config_env.py \
  tests/test_png_tools.py \
  tests/test_upload_flow.py \
  -q
```

## Current API

```text
GET  /api/health
POST /api/upload-m30-preview
GET  /api/tasks/{taskId}
GET  /api/tasks/{taskId}/dsl
GET  /api/tasks/{taskId}/m29-direct-dsl
GET  /api/tasks/{taskId}/m30-materialization
GET  /api/assets/{assetId}
GET  /files/uploads/*
GET  /files/assets/*
```

`/api/upload-m30-preview` validates a PNG, stores it at `storage/uploads/{taskId}/original.png`, creates a `processing` task, and runs the preview pipeline in a FastAPI background task.

On success, the task reaches:

```text
status = completed
stage = m30_completed
progress = 100
```

`GET /api/tasks/{taskId}/dsl` returns `storage/m30_1_uploads/{taskId}/m30/m30_materialized_dsl.json`.

`GET /api/tasks/{taskId}/m29-direct-dsl` returns the experiment variant from `storage/m30_1_uploads/{taskId}/m29_direct/m29_direct_replay_dsl.json` plus report summary, warnings, output report path, and stage timings. It is used by plugin `Generate Compare`; it is not the default product DSL.

`GET /api/tasks/{taskId}/m30-materialization` returns the M30 report summary, warnings, skipped items, output DSL path, optional debug preview path, and `stage_timings.json`.

The removed routes below are not current API:

```text
POST /api/upload
GET /api/tasks/{taskId}/m31-reconstruction
GET /api/tasks/{taskId}/m39-boundary-classification
GET /api/tasks/{taskId}/m39-1-unit-structure-readiness
old M8-M28 debug endpoints
```

## Current Pipeline

The upload preview pipeline runs:

```text
OCR
-> raw M29 visual primitive graph
-> M29.2 source-level UI physical graph
-> M29.3 relation graph report
-> M29.4 stable design cluster report
-> M29.5 replay plan
-> M29 Direct replay variant
-> publish M29 Direct assets under /files/assets/{taskId}/m29_direct/
-> M29.1 symbol fragment grouping
-> M29.0.2 text-masked media audit
-> M29.0.3 visual evidence normalization with lineage
-> M29.0.7 text/visual ownership gate
-> M29.0.4 visual object candidate audit with ownership routing
-> M29.0.5 text-aware visual object refinement
-> M30 evidence-grounded DSL materialization
-> publish M30 image assets under /files/assets/{taskId}/m30/
```

It deliberately does not run old pre-M29 diagnostic stages, removed M31-M39 downstream stages, fallback masking, Auto Layout, Figma Components, SVG/vectorization, or icon recovery.

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

In the preview pipeline, OCR is required evidence. If the configured OCR provider fails, the task is marked `failed`; the backend does not create a fake completed M30 DSL.

Baidu OCR polygon metadata is kept as evidence:

```text
OCRBlock.meta.angle
OCRBlock.meta.polygon
```

## M30 Preview Profile

```bash
M30_PREVIEW_PROFILE=production   # default plugin preview runtime
M30_PREVIEW_PROFILE=development  # full diagnostics for local debugging
```

`production` keeps OCR JSON, structured M29/M29.0.x/M30 JSON, M29.0.5 formal visual assets needed by M30, M29 Direct artifacts when available, published renderer assets, M30 DSL/report, and `stage_timings.json`. It skips overlays, preview sheets, review/contact sheets, and M30 preview PNGs.

`development` preserves full diagnostic output. Single-stage M29/M30 scripts still default to development-style output through their own function defaults.

## M29 Direct

M29 Direct is protected by the M29 contract chain:

```text
raw M29
-> M29.2 source ownership
-> M29.3 region relation
-> M29.4 weak cluster
-> M29.5 replay plan
-> M29 Direct materialization
```

M29.2 classifies source pixel ownership into editable text, preserved raster text, media, raster icons, stable UI shapes, and diagnostic-only objects. M29.5 decides visible replay actions, deduplication, ordering, node budget, and cleanup authorization. M29.4 remains weak structural evidence; it does not grant component, Auto Layout, or Figma Component/Instance permission.

## M30 Materialization

M30 is the bridge from trusted M29.0.5 evidence into existing DSL v0.1. It consumes:

```text
textMembers
shapeCandidates
safe visualAssets
composite media candidates
```

It does not consume mixed/future/audit-only evidence as visible DSL children. Those references may appear only in reports or DSL meta.

Safe visual assets are emitted as DSL `image` nodes, not `icon` nodes, because the current renderer does not implement an `icon` DSL type for this path.

M30 text materialization has an explicit editability decision:

```text
editable_text
graphic_text_preserve_in_fallback
review_text
```

Only `editable_text` creates a visible `m30_text_member`. `graphic_text_preserve_in_fallback` and `review_text` stay in fallback and are reported; they are not included in fallback pixel erasure.

M30 samples `style.color` for each emitted editable text node from source pixels. If no foreground pixels are available, it falls back to black or white based on background brightness. If sampling fails, it uses the configured default text color and records that fallback in node meta/report summary.

M30.6 allows only large `assetUse=image_asset` entries from M29.0.5 to become `m30_visual_asset` DSL image nodes when their text overlap is below `M30_ACCEPTED_IMAGE_MAX_TEXT_OVERLAP`, their area is above `M30_ACCEPTED_IMAGE_MIN_AREA`, they have no high-risk text/boundary flags, and lineage resolves back to a raw M29 image node.

M30.7 keeps independent media layers clean. It fills editable text bboxes inside copied `m30_visual_asset`/`m30_composite_media_asset` PNGs with sampled local background, so dragging the text does not reveal baked duplicate text underneath. It also materializes large `decision=partially_separated` objects with `combinedAssetPath` as `m30_composite_media_asset`.

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
```

Each upload task may include:

```text
storage/m30_1_uploads/{taskId}/ocr/
storage/m30_1_uploads/{taskId}/m29/
storage/m30_1_uploads/{taskId}/m29_2/
storage/m30_1_uploads/{taskId}/m29_3/
storage/m30_1_uploads/{taskId}/m29_4/
storage/m30_1_uploads/{taskId}/m29_5/
storage/m30_1_uploads/{taskId}/m29_direct/
storage/m30_1_uploads/{taskId}/m29_1/
storage/m30_1_uploads/{taskId}/m29_0_2/
storage/m30_1_uploads/{taskId}/m29_0_3/
storage/m30_1_uploads/{taskId}/m29_0_7/
storage/m30_1_uploads/{taskId}/m29_0_4/
storage/m30_1_uploads/{taskId}/m29_0_5/
storage/m30_1_uploads/{taskId}/m30/
storage/m30_1_uploads/{taskId}/stage_timings.json
```

Renderer-fetchable image assets are published to:

```text
storage/assets/{taskId}/m30/
storage/assets/{taskId}/m29_direct/
http://localhost:8000/files/assets/{taskId}/m30/...
http://localhost:8000/files/assets/{taskId}/m29_direct/...
```

## Removed Legacy Surface

M30.2.2 permanently removed the frozen pre-M29 backend chain from active source. M29 backend downstream pruning removed the later downstream structure experiments. History remains in git, old ADRs, completed plans, and `docs/reference/legacy/`.

Do not restore these as product paths without a new plan and tests:

```text
POST /api/upload
old M8-M28 task debug endpoints
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
