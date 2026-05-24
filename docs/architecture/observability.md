# 可观测性

v0.1 只做能定位问题的日志和 artifact，不做完整监控平台。

## Current Upload Diagnostics

当前 `/api/upload-m30-preview` 的主要诊断入口：

```text
storage/m30_1_uploads/{taskId}/stage_timings.json
GET /api/tasks/{taskId}/m29-direct-dsl
GET /api/tasks/{taskId}/m30-materialization
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
```

M31/M37/M38/M39/M39.1 stage timings are historical and should not appear in new upload tasks.

## M29 Direct Diagnostics

M29.2 writes:

```text
storage/m30_1_uploads/{taskId}/m29_2/source_ui_physical_graph.json
storage/m30_1_uploads/{taskId}/m29_2/source_ui_physical_graph_overlay.png
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

Each source object records `visualKind`, `pixelOwner`, `replayDecision`, `sourceEvidence`, `confidence`, `reasons`, and `risks`. If M29 Direct renders ordinary UI text as raster or turns art text into generic text, inspect this report before changing M30, renderer, or plugin behavior.

M29.3.1 writes:

```text
storage/m30_1_uploads/{taskId}/m29_3/region_relation_graph_report.json
```

M29.4 writes:

```text
storage/m30_1_uploads/{taskId}/m29_4/stable_design_cluster_report.json
```

M29.5 writes:

```text
storage/m30_1_uploads/{taskId}/m29_5/replay_plan.json
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

M29 Direct writes:

```text
storage/m30_1_uploads/{taskId}/m29_direct/m29_direct_replay_dsl.json
storage/m30_1_uploads/{taskId}/m29_direct/m29_direct_replay_report.json
storage/assets/{taskId}/m29_direct/*
```

The report summary includes:

```text
m29NodeCount
ocrTextCount
replayedTextCount
replayedImageCount
replayedSymbolCount
replayedShapeCount
skippedBlockedCount
skippedDuplicateCount
fallbackErasedBBoxCount
visibleNodeCount
maxTotalVisibleNodesExceeded
m292SourcePhysicalGraph
```

If `m29_direct_replay` or `m29_direct_asset_publish` fails, the failed stage remains visible in `stage_timings.json`. This does not necessarily fail the upload task because M29 Direct is a non-blocking compare variant.

## M30 Diagnostics

`GET /api/tasks/{taskId}/m30-materialization` returns the M30 report plus the same stage timings.

M30 text editability diagnostics:

```text
textEditabilityDecisions
preservedGraphicTextItems
reviewTextItems
summary.editableTextCount
summary.preservedGraphicTextCount
summary.reviewTextCount
summary.textEditabilityReasonCounts
```

These fields answer why an OCR/M29 text evidence item became editable text or remained in raster fallback.

M30 text-symbol leakage diagnostics:

```text
textSymbolLeakageDecisions
summary.trimmedTextSymbolLeakageCount
summary.reviewTextSymbolLeakageCount
summary.textSymbolLeakageReasonCounts
```

M30 foreground sampling diagnostics:

```text
text node meta.textForegroundColorSource
summary.sampledTextForegroundCount
summary.defaultContrastTextForegroundCount
summary.defaultTextColorFallbackCount
```

M30 image/composite media diagnostics:

```text
summary.materializedAcceptedImageCount
summary.materializedCompositeMediaCount
summary.cleanedMaterializedImageAssetCount
summary.erasedTextFromMaterializedImageAssetCount
summary.skippedCompositeMediaCount
materializedImageNodes[]
skippedItems[]
warnings[]
```

If a large product or banner image is not draggable, inspect `skippedItems[]` before changing M29 detection. If editable text shows a ghost after dragging, inspect `cleanedMaterializedImageAssetCount` and warnings starting with `m30_image_asset_text_erasure_`.

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

M8-M28、M31-M39/M39.1 和 ONNX proposer 的历史日志字段只在 ADR、completed plans、git history 或旧本地 storage 中有意义。当前 backend runtime 不再生成这些 reports，也不提供对应 diagnostic endpoints。
