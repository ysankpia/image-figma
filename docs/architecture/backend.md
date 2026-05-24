# 后端架构

后端负责接收单张 PNG、运行 OCR 与 M29/M30 证据链、保存 DSL/资产，并通过 API 提供给 Figma 插件。当前阶段已经剪掉 M31-M39/M39.1 downstream experiments；这些历史阶段不再是 backend runtime。

## Runtime Surface

当前运行面：

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

已移除的接口不再通过环境变量复活，包括旧 `POST /api/upload`、旧 M8-M28 debug endpoints，以及 M31/M39/M39.1 downstream diagnostics endpoints。

## Processing Pipeline

当前 `POST /api/upload-m30-preview` 后台链路：

```text
receive multipart PNG
-> validate MIME, PNG signature, size, and IHDR metadata
-> save uploads/{taskId}/original.png
-> create task status=processing stage=m30_queued
-> OCR
-> raw M29 visual primitive graph
-> M29.2 source-level UI physical graph
-> M29.3.1 source relation graph report
-> M29.4 stable design cluster report
-> M29.5 replay quality plan
-> M29 Direct replay compare variant
-> publish M29 Direct assets
-> M29.1 symbol fragment grouping
-> M29.0.2 text-masked media audit
-> M29.0.3 visual evidence normalization with M29.1 lineage
-> M29.0.7 text/visual ownership gate
-> M29.0.4 visual object candidate audit with ownership routing
-> M29.0.5 text-aware visual object refinement
-> M30 evidence-grounded DSL materialization
-> publish M30 assets
-> save dsl_results path to m30/m30_materialized_dsl.json
-> mark task completed
```

M29.2-M29.5 是当前 source truth experiment chain。M29 Direct 消费这条链路，输出 compare variant。M29.0.x + M30 是迁移期 legacy `/dsl` bridge，保留插件默认 DSL 出口，但不反向决定 M29 source ownership。

当前链路不运行：

```text
removed pre-M29 upload chain
M29.1.1 pre-OCR lineage audit
M29.0.6 member boundary quality audit
M29.0.3.2 residual mixed boundary review
M31 reconstruction diagnostics
M37 hierarchy readiness
M38 hierarchy materialization
M39 content/chrome classification
M39.1 unit structure readiness
ONNX proposer
Auto Layout
Figma Component/Instance
SVG/vectorization
icon recovery
```

`mixed_symbol_text_conflict_audit.py` 仍保留，因为 M30 materialization 使用其中的 forbidden contract term guard。它不是当前 upload pipeline stage。

## M29 Source Truth

Raw M29 输出 text/shape/image/symbol/unknown primitives、support backgrounds、shape geometry fit、assets 和 report artifacts。它只描述源图像中的物理证据，不生成 DSL visible nodes。

M29.2 输出 source objects：

```text
visualKind
pixelOwner
replayDecision
sourceEvidence
confidence
reasons
risks
```

M29.3.1 是纯 bbox relation graph report。M29.4 是 weak structural evidence report。M29.5 是 replay plan quality gate，负责去重、排序、node budget 和 cleanup 授权。

这些阶段共同保护 M29 Direct。它们目前不替换 `/api/tasks/{taskId}/dsl`。

## M29 Direct

M29 Direct Replay 写入：

```text
storage/m30_1_uploads/{taskId}/m29_direct/m29_direct_replay_dsl.json
storage/m30_1_uploads/{taskId}/m29_direct/m29_direct_replay_report.json
storage/assets/{taskId}/m29_direct/
```

读取接口：

```text
GET /api/tasks/{taskId}/m29-direct-dsl
```

M29 Direct 失败是非阻塞的：stage timing 记录失败，主线 M30 `/dsl` 仍可完成。若 variant 或 asset publish 不存在，接口返回 `M29_DIRECT_DSL_NOT_FOUND`。

## Legacy M30 Bridge

当前 `/api/tasks/{taskId}/dsl` 仍由 M29.0.x + M30 materialization 生成：

```text
M29.1 / M29.0.2 / M29.0.3 / M29.0.7 / M29.0.4 / M29.0.5
-> M30 evidence-grounded DSL materialization
```

M30 materializes trusted text、shape、image 和 composite media evidence into DSL v0.1。它会保留 fallback，记录 text editability decision，发布 M30 copied assets，并对已物化的 copied media asset 做局部文字去重清理。

M30 仍是迁移期 bridge。后续若要把 `/dsl` 转成 M29.5 plan-driven materializer，必须单独开阶段，不在本剪枝阶段混做。

## Artifact Profiles

`M30_PREVIEW_PROFILE=production` 是默认插件 preview profile：

```text
keep OCR JSON
keep structured M29/M29.0.x/M30 JSON
keep M29.0.5 formal assets needed by M30
keep M29 Direct DSL/report and published assets when available
keep M30 DSL/report and published assets
keep stage_timings.json
skip overlays, preview sheets, review/contact sheets, M30 preview PNG
```

`development` 保留完整诊断 artifacts。profile 只影响 artifacts，不改变 OCR、M29 classification、DSL schema 或 Renderer 行为。

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

每个 preview task 当前可能写入：

```text
storage/uploads/{taskId}/original.png
storage/m30_1_uploads/{taskId}/ocr/ocr.json
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
storage/assets/{taskId}/m30/
storage/assets/{taskId}/m29_direct/
```

`backend/storage/` 是 runtime/diagnostic data，不提交。

## Task State

当前 task status：

```text
processing
completed
failed
```

当前 stage names：

```text
m30_queued
ocr
m29
m29_2_source_ui_physical_graph
m29_3_relation_graph_report
m29_4_stable_design_cluster
m29_5_replay_plan
m29_direct_replay
m29_direct_asset_publish
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

`stage_timings.json` 记录 `stage`、start/end timestamps、elapsed seconds、status 和 error metadata。

## Failure Strategy

Upload validation failures reject the request before a task is created:

```text
invalid MIME
invalid PNG signature
unreadable PNG dimensions
file too large
```

OCR 是当前 preview path 的 required evidence。missing Baidu token、unsupported OCR provider、remote OCR failure 或 timeout 都会让任务失败，不生成 fake completed DSL。

M29/M29.0.x/M30 required stages should fail fast when required artifacts or contracts are invalid. Optional M29 Direct stages may fail without blocking `/dsl`。

## Database

SQLite stores only current runtime indexes:

```text
tasks
assets
dsl_results
ocr_results
error_logs
```

Large stage payloads remain JSON files under `storage/m30_1_uploads/{taskId}/`。

## Boundaries

Backend generates DSL and assets. It does not operate the Figma canvas.

Renderer consumes DSL only. It does not run OCR, M29, materialization, asset slicing, or quality gates.

Plugin UI treats backend pipeline details as task status and does not depend on internal M29/M30 JSON.
