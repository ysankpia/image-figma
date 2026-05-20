# 后端架构

后端负责接收 PNG、创建任务、运行 OCR + M29 + M31 diagnostics + M30、保存 DSL 和资产，并通过 API 提供给 Figma 插件。

## Runtime Surface

当前默认运行面只有：

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

`POST /api/upload` 和旧 M8-M28 debug endpoints 已在 M30.2.2 移除。后端不再提供环境变量复活旧路径。

## Processing Pipeline

M30.1 plugin preview upload pipeline:

```text
receive multipart PNG at /api/upload-m30-preview
-> validate MIME, PNG signature, size, and IHDR metadata
-> save uploads/{taskId}/original.png
-> create task status=processing stage=m30_queued
-> OCR
-> M29 visual primitive graph
-> M31 reconstruction diagnostics
-> M29.1 symbol fragment grouping
-> M29.0.2 text-masked media audit
-> M29.0.3 visual evidence normalization with M29.1 lineage
-> M29.0.7 text/visual ownership gate
-> M29.0.4 visual object candidate audit with ownership routing
-> M29.0.5 text-aware visual object refinement
-> M30 evidence-grounded DSL materialization with text editability decisions and fallback erasure only for editable text
-> copy local M30 DSL assets to assets/{taskId}/m30 and rewrite URLs
-> save dsl_results path to m30/m30_materialized_dsl.json
-> mark task completed
```

This is the product preview path. It deliberately does not run:

```text
M29.1.3 mixed conflict audit
M29.0.3.2 residual mixed review
M29.0.6 member boundary quality audit
removed pre-M29 upload chain
Auto Layout
Figma Component/Instance
SVG/vectorization
icon recovery
```

M31 reconstruction UI tree is a runtime diagnostic side path. It consumes only source PNG, OCR JSON/document, and M29 `nodes.json`/document, writes report artifacts, and does not change M30 DSL or renderer output.

M31.1.1 ensures the source PNG is decoded once into `PngPixels`; unit fallback crops are sliced from decoded rows and then encoded as PNG. M31 fallback generation must not call compressed PNG crop helpers per unit.

M34.1 keeps OCR text evidence in the source chain. Rotated or graphic text is not dropped before M29. Instead, M30 writes a text editability decision for each text member:

```text
editable_text
graphic_text_preserve_in_fallback
review_text
```

Only `editable_text` becomes visible `m30_text_member` and participates in fallback pixel erasure. Preserved graphic text remains inside the fallback image and appears in the M30 report for audit.

## Artifact Profiles

`M30_PREVIEW_PROFILE=production` is the default for plugin preview.

```text
production:
  keep OCR JSON
  keep structured M29/M30 JSON
  keep M29.0.5 formal assets needed by M30
  keep M30 DSL/report
  keep published renderer assets
  keep stage_timings.json
  skip overlays, preview sheets, review/contact sheets, M30 preview PNG

development:
  keep full diagnostic output
```

The profile changes artifacts only. It does not change OCR, M29 classification rules, DSL schema, or renderer behavior.

## Storage

Development storage is local:

```text
backend/storage/
  uploads/
  assets/
  dsl/
  ocr/
  logs/
  m30_1_uploads/
```

Each M30 preview task writes:

```text
storage/uploads/{taskId}/original.png
storage/m30_1_uploads/{taskId}/ocr/ocr.json
storage/m30_1_uploads/{taskId}/m29/
storage/m30_1_uploads/{taskId}/m31/
storage/m30_1_uploads/{taskId}/m29_1/
storage/m30_1_uploads/{taskId}/m29_0_2/
storage/m30_1_uploads/{taskId}/m29_0_3/
storage/m30_1_uploads/{taskId}/m29_0_7/
storage/m30_1_uploads/{taskId}/m29_0_4/
storage/m30_1_uploads/{taskId}/m29_0_5/
storage/m30_1_uploads/{taskId}/m30/
storage/m30_1_uploads/{taskId}/stage_timings.json
storage/assets/{taskId}/m30/
```

`backend/storage/` is diagnostic/runtime data and must not be committed.

M31 manual runs write outside the task runtime by default:

```text
storage/m31_runs/{taskId}/m31_reconstruction_tree.json
storage/m31_runs/{taskId}/m31_reconstruction_tree_report.json
storage/m31_runs/{taskId}/m31_unit_fallback_assets/
```

## Task State

Current task status values:

```text
processing
completed
failed
```

Current stage names are concrete pipeline stages, for example:

```text
m30_queued
ocr
m29
m31_reconstruction
m29_1
m29_0_2
m29_0_3
m29_0_7
m29_0_4
m29_0_5
m30_materialization
m30_asset_publish
m30_completed
```

`stage_timings.json` records `stage`, start/end timestamps, elapsed seconds, status, and error metadata for each stage.

## Failure Strategy

Upload validation failures reject the request before a task is created:

```text
invalid MIME
invalid PNG signature
unreadable PNG dimensions
file too large
```

Background pipeline failures mark the task as failed and write `error_logs`.

In the current M30 preview path, OCR is required evidence. A missing Baidu token, unsupported OCR provider, remote OCR failure, or OCR timeout fails the M30 preview task instead of emitting a fake completed DSL.

M29/M30 stages should fail fast when their required source artifacts or contracts are invalid. The product path should not fabricate visible nodes from audit-only or missing evidence.

M31 diagnostics are optional by default. If `M31_UPLOAD_DIAGNOSTICS_STRICT=false`, M31 failure writes a failed `m31_reconstruction` timing and an `error_logs` row, then the pipeline continues to M30 DSL. If `M31_UPLOAD_DIAGNOSTICS_STRICT=true`, M31 failure marks the task failed at `stage=m31_reconstruction`.

## Database

SQLite stores only current runtime indexes:

```text
tasks
assets
dsl_results
ocr_results
error_logs
```

Large stage payloads remain JSON files under `storage/m30_1_uploads/{taskId}/`.

M30.2.2 does not perform database migrations or local storage cleanup. Existing old local tables/files may remain on a developer machine, but active source no longer creates or consumes the removed pre-M29 result tables.

## Boundaries

Backend generates DSL and assets. It does not operate the Figma canvas.

Renderer consumes DSL only. It does not run OCR, M29, asset slicing, or quality gates.

Plugin UI treats backend pipeline details as task status and does not depend on M29/M30 internal JSON.
