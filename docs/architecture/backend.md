# 后端架构

后端负责接收单张 PNG、运行 OCR 与 M29 证据链、保存 DSL/资产，并通过 API 提供给 Figma 插件。当前阶段已经把产品主链收口为 M29 plan-driven materialization；旧 M30 materializer、M29 Direct compare、M31-M39/M39.1 downstream experiments 不再是 backend runtime。

## Runtime Surface

当前运行面：

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

`POST /api/upload-preview` 是历史命名的兼容入口。它当前运行 M29 mainline，不运行 legacy M30 product path。

已移除的接口不再通过环境变量复活，包括：

```text
POST /api/upload
GET /api/tasks/{taskId}/m29-direct-dsl
GET /api/tasks/{taskId}/m30-materialization
GET /api/tasks/{taskId}/m31-reconstruction
GET /api/tasks/{taskId}/m39-boundary-classification
GET /api/tasks/{taskId}/m39-1-unit-structure-readiness
old M8-M28 debug endpoints
```

## Processing Pipeline

当前 `POST /api/upload-preview` 后台链路：

```text
receive multipart PNG
-> validate MIME, PNG signature, size, and IHDR metadata
-> save uploads/{taskId}/original.png
-> create task status=processing stage=m29_queued
-> OCR
-> raw M29 visual primitive graph
-> M29.2 source-level UI physical graph
-> M29.3.1 source relation graph report
-> M29.4 stable design cluster report
-> M29.5 replay quality plan
-> M29 plan-driven DSL materialization
-> publish M29 assets
-> save dsl_results path to materialized_design/design.dsl.json
-> mark task completed stage=m29_completed
```

当前链路不运行：

```text
removed pre-M29 upload chain
M29 Direct compare replay
M29.1 / M29.0.x legacy bridge
M30 evidence-grounded materialization
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

M29.4 的 cluster role hint 不提供组件化、Auto Layout、Figma Component/Instance 或直接 materialization 权限。它只能进入 M29.5 plan 的解释性 `clusterIds`。

## M29 Plan-Driven Materialization

`backend/app/m29_plan_materializer.py` 是当前正式 DSL producer。它的输入只来自：

```text
source PNG
OCR
raw M29
M29.2
M29.3
M29.4
M29.5 replay plan
```

它只执行 M29.5 plan：

```text
text_replay -> role=m29_text
shape_replay -> role=m29_shape
image_replay -> role=m29_image
icon_replay -> role=m29_symbol
preserve_in_parent_raster / fallback_only / diagnostic_only / suppress_duplicate -> no visible node
```

可见层顺序由 plan 控制：

```text
background/support shape -> raster/media image -> icon -> text
```

Materializer 负责：

- 从 source PNG 边缘样本推导 root/page 背景，避免 fallback-off 时固定浅色坍塌。
- 复制或裁切 plan-approved raster/media/icon assets。
- 只对 plan-approved visible actions 创建 DSL nodes。
- 只按 M29.5 `cleanupTargets` 执行 fallback erasure 和 copied image asset cleanup。
- 写出 `materialization_report.json` 供诊断。

Materializer 不负责：

```text
重新判断 text editability
重新判断 contains/overlap cleanup
发明新 bbox
按主题、颜色、截图、文案或行业特化
把 cluster 变成 component/container
```

## Artifact Profiles

`UPLOAD_PREVIEW_PROFILE=production` 是默认插件 preview profile：

```text
keep OCR JSON
keep structured M29/M29.2/M29.3/M29.4/M29.5 JSON
keep M29 materialized DSL/report and published assets
keep stage_timings.json
skip raw M29 overlays and preview sheets when possible
```

`development` 保留 raw M29 诊断 artifacts。profile 只影响 artifacts，不改变 OCR、M29 classification、DSL schema 或 Renderer 行为。

`UPLOAD_PREVIEW_PROFILE` 仅作为兼容 alias 被读取；新配置应使用 `UPLOAD_PREVIEW_PROFILE`。

## Storage

Development storage is local:

```text
backend/storage/
  uploads/
  assets/
  dsl/
  ocr/
  logs/
  upload_previews/
```

每个 preview task 当前可能写入：

```text
storage/uploads/{taskId}/original.png
storage/upload_previews/{taskId}/ocr/ocr.json
storage/upload_previews/{taskId}/m29/
storage/upload_previews/{taskId}/m29_2/
storage/upload_previews/{taskId}/m29_3/
storage/upload_previews/{taskId}/m29_4/
storage/upload_previews/{taskId}/m29_5/
storage/upload_previews/{taskId}/materialized_design/
storage/upload_previews/{taskId}/stage_timings.json
storage/assets/{taskId}/m29/
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

M29 required stages and M29 plan materialization should fail fast when required artifacts or contracts are invalid. The current product path no longer has a non-blocking compare materializer that can fail silently while `/dsl` succeeds.

## Database

SQLite stores only current runtime indexes:

```text
tasks
assets
dsl_results
ocr_results
error_logs
```

Large stage payloads remain JSON files under `storage/upload_previews/{taskId}/`。

## Boundaries

Backend generates DSL and assets. It does not operate the Figma canvas.

Renderer consumes DSL only. It does not run OCR, M29, materialization, asset slicing, or quality gates.

Plugin UI treats backend pipeline details as task status and does not depend on internal M29 JSON.
