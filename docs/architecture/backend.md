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
-> M30 evidence-grounded DSL materialization with text editability decisions, accepted image materialization, copied media asset text cleanup, composite media materialization, and fallback erasure for materialized nodes
-> copy local M30 DSL assets to assets/{taskId}/m30 and rewrite URLs
-> M39 content-chrome boundary classification, classifies M30 nodes as chrome or content using relative geometry rules and optional ONNX model proposer
-> M37 hierarchy readiness diagnostic, if M31 artifacts exist
-> M38 controlled hierarchy materialization, if M37 report exists and M38 is enabled; skips units with boundary_classification_conflict
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

M34.2 adds context-aware counter signals to reduce false-positive preservation of ordinary UI text. The policy uses relative bbox geometry and local pixel metrics:

```text
aligned_text_row
compact_overlay_badge
metadata_text_cluster
stable_local_background
```

These signals can override weak preserve signals such as light OCR angle noise or image containment. They do not use business words, fixed coordinates, or fixed-resolution pixel constants.

M36 samples foreground color for emitted editable text from source PNG pixels. It uses local dominant background and high-contrast interior pixels, then writes the sampled color to DSL text `style.color`. Preserved graphic text is not sampled or redrawn.

M34.3 cleans high-confidence leading text-symbol leakage before M30 emits editable text. OCR and M29 evidence stay unchanged; M30 may trim a leading uppercase `Q` only when source pixels show a projection gap between a left symbol-like ink group and the right text ink group. The emitted text node uses `cleanedBBox`, so fallback erasure naturally leaves the protected symbol pixels in the fallback image. M34.3 does not modify M31 or create icon layers.

M30.6 is an internal M30 image materialization policy. It does not add a runtime stage. It allows only large `assetUse=image_asset` entries from M29.0.5 to bypass the old zero text-overlap visual-asset gate when their overlap is below `M30_ACCEPTED_IMAGE_MAX_TEXT_OVERLAP`, their area is above `M30_ACCEPTED_IMAGE_MIN_AREA`, they have no high-risk text/boundary flags, and lineage resolves back to a raw M29 image node such as `image_003`.

M30.6 writes recovered ids into the emitted image node meta, including the extended `sourceEvidenceNodeIds` list consumed by M37. It does not run OCR, does not recover image-internal overlays, does not fix `1/6`, does not clean parent image internals, and does not change M37/M38 grouping policy.

M30.7 is also an internal M30 policy, not a runtime stage. It enforces raster pixel ownership after media materialization:

```text
editable text layer exists above copied media asset
-> same text pixels must be removed from the copied media asset underneath
```

The cleanup edits only M30 copied assets under `m30/assets/`, never M29.0.5 source assets. It maps editable text bboxes into local image pixels and fills those bboxes with local background samples. M30.7 also materializes large M29.0.5 `partially_separated` objects with `combinedAssetPath` as `role=m30_composite_media_asset` image nodes, so carousel/banner blocks can be selected and dragged as single raster layers. It does not split their internal art text into editable text.

M37 is a read-only hierarchy readiness side path. It reads M31 tree/report and the final M30 DSL/report, then writes `m37_hierarchy_readiness_report.json`. It does not modify DSL, create visible frames, or change Renderer coordinate semantics.

M38 is the first controlled hierarchy materialization stage. It consumes only M37 safe direct-match candidates, creates transparent DSL `group` containers, and moves existing M30 children under those containers with parent-local coordinates. It preserves absolute page bboxes in `rawLayout`/meta, does not change assets, does not run OCR or visual detection, and does not mutate M37 artifacts.

M39 is the content-chrome boundary classification stage. It runs between M30 asset publish and M37 hierarchy readiness. It reads the M30 DSL and optionally the source PNG, classifies each M30 DSL node as `"chrome"` or `"content"` in the node `meta.boundaryClassification` field using:

```text
relative geometry rules (top/bottom 12% full-width spans, right-edge floats)
optional ONNX model proposer (YOLOv8, non-blocking, dynamically loaded)
```

M37 uses M39 labels to mark reconstruction units that contain both chrome and content nodes as unsafe (`boundary_classification_conflict`). M38 skips those units. M39 does not create visible elements, does not move nodes, does not change assets. If `onnxruntime` is not installed, M39 falls back to rule-only classification silently.

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
storage/m30_1_uploads/{taskId}/m37/
storage/m30_1_uploads/{taskId}/m38/
storage/m30_1_uploads/{taskId}/m39/
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
m39_boundary_classification
m37_hierarchy_readiness
m38_hierarchy_materialization
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
