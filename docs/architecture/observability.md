# 可观测性

v0.1 只做能定位问题的日志和 artifact，不做完整监控平台。

## Current Upload Diagnostics

当前 `/api/upload-preview` 的主要诊断入口：

```text
storage/upload_previews/{taskId}/stage_timings.json
GET /api/tasks/{taskId}/materialization
```

`stage_timings.json` 记录每个 stage 的开始时间、结束时间、耗时、状态、错误码和错误消息。

当前 stage timing 可能包含：

```text
ocr
m29
m29_2_source_ui_physical_graph
m29_3_relation_graph_report
m29_4_stable_design_cluster
m29_5_replay_plan
m29_materialization
m29_asset_publish
```

M29 Direct、M29.0.x、M30、M31/M37/M38/M39/M39.1 stage timings are historical and should not appear in new upload tasks.

## M29 Source Diagnostics

M29 writes:

```text
storage/upload_previews/{taskId}/m29/nodes.json
```

In development profile, raw M29 may also write overlays and preview sheets.

M29.2 writes:

```text
storage/upload_previews/{taskId}/m29_2/source_ui_physical_graph.json
storage/upload_previews/{taskId}/m29_2/source_ui_physical_graph_overlay.png
```

The report summary includes:

```text
sourceObjectCount
m29NodeCount
ocrTextCount
editableTextCount
preservedRasterTextCount
rasterIconCount
mediaRegionCount
shapeGeometryCount
diagnosticOnlyCount
dslChanged
assetChanged
```

Each source object records `visualKind`, `pixelOwner`, `replayDecision`, `sourceEvidence`, `confidence`, `reasons`, and `risks`. If current output renders ordinary UI text as raster, loses a media block, or redraws a complex foreground as a flat shape, inspect this report before changing the materializer, renderer, or plugin behavior.

M29.3.1 writes:

```text
storage/upload_previews/{taskId}/m29_3/region_relation_graph_report.json
```

M29.4 writes:

```text
storage/upload_previews/{taskId}/m29_4/stable_design_cluster_report.json
```

M29.5 writes:

```text
storage/upload_previews/{taskId}/m29_5/replay_plan.json
```

Its summary focuses on replay quality:

```text
plannedVisibleNodeCount
plannedTextReplayCount
plannedImageReplayCount
plannedIconReplayCount
plannedShapeReplayCount
suppressedDuplicateCount
fallbackCleanupTargetCount
copiedImageAssetCleanupTargetCount
clusterSupportedPlanItemCount
nodeBudgetSuppressedCount
```

## M29 Materialization Diagnostics

M29 plan-driven materializer writes:

```text
storage/upload_previews/{taskId}/materialized_design/design.dsl.json
storage/upload_previews/{taskId}/materialized_design/materialization_report.json
storage/assets/{taskId}/m29/*
```

`GET /api/tasks/{taskId}/materialization` returns the same report plus stage timings.

The report summary includes:

```text
m29NodeCount
ocrTextCount
replayedTextCount
replayedImageCount
replayedSymbolCount
replayedShapeCount
fallbackErasedBBoxCount
copiedImageAssetTextErasedCount
visibleNodeCount
maxTotalVisibleNodesExceeded
m292SourcePhysicalGraph
m295ReplayPlan
```

If fallback-off output collapses to a wrong background, inspect:

```text
dsl.page.background.value
dsl.root.style.fill
fallback asset pixels
replayedImageCount
replayedShapeCount
skippedItems[]
```

If dragging editable text reveals baked duplicate text inside a copied media asset, inspect:

```text
m295ReplayPlan.copiedImageAssetCleanupTargetCount
summary.copiedImageAssetTextErasedCount
replayedNodes[]
planItems[].cleanupTargets
```

## Logs

后端任务日志至少包含：

- `taskId`
- `stage`
- `status`
- `errorCode`
- `message`
- `detail`
- `durationMs`
- `createdAt`

Renderer warning 至少包含：

- `elementId`
- `type`
- `code`
- `message`

百度 PP-OCRv5 provider 的 OCR JSON `meta` 还应包含远端 `jobId`、提交耗时、轮询耗时、轮询次数和低置信度过滤数量，方便定位远端耗时和质量问题。

## Historical Diagnostics

M8-M28、M29 Direct、M29.0.x、M30、M31-M39/M39.1 和 ONNX proposer 的历史日志字段只在 ADR、completed plans、git history 或旧本地 storage 中有意义。当前 backend runtime 不再生成这些 reports，也不提供对应 diagnostic endpoints。
