# 可观测性

v0.1 只做能定位问题的日志，不做完整监控平台。

## Current Upload Diagnostics

当前 `/api/upload-m30-preview` 的主要诊断入口是：

```text
storage/m30_1_uploads/{taskId}/stage_timings.json
GET /api/tasks/{taskId}/m29-direct-dsl
GET /api/tasks/{taskId}/m30-materialization
GET /api/tasks/{taskId}/m31-reconstruction
```

`stage_timings.json` 记录每个 stage 的开始时间、结束时间、耗时、状态、错误码和错误消息。M31.1 增加 `m31_reconstruction` stage，用来观察 M29 primitive evidence 是否能组织成 reconstruction units。

M31 reconstruction report 至少观察：

```text
primitiveRefCount
unitCount
reviewBucketCount
primitiveOwnershipRate
orphanPrimitiveCount
rootLeafPrimitiveCount
unitFallbackCoverage
createdDetectionBBoxCount
permissionViolationCount
forbiddenHitCount
```

这些是结构质量指标，不是视觉相似度指标。M31 默认非阻塞失败；失败时 `stage_timings.json` 会记录 failed `m31_reconstruction`，同时写入 `error_logs`。

M31.1.1 修正了 fallback crop 性能路径：unit fallback crops 从已解码 `PngPixels` 裁剪，不再对每个 unit 重新解码整张 PNG。若同类图的 `m31_reconstruction` 再次接近百秒，应优先检查是否回退到了 compressed PNG crop path。

M29 Direct Replay compare mode adds two stages to `stage_timings.json`:

```text
m29_2_source_ui_physical_graph
m29_3_relation_graph_report
m29_4_stable_design_cluster
m29_5_replay_plan
m29_direct_replay
m29_direct_asset_publish
```

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

Each source object records `visualKind`, `pixelOwner`, `replayDecision`, `sourceEvidence`, `confidence`, `reasons`, and `risks`. If the M29 direct side renders ordinary UI text as raster or turns art text into generic text, inspect this report before changing downstream M30/M39 rules.

It writes:

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

The read-only API endpoint is:

```text
GET /api/tasks/{taskId}/m29-direct-dsl
```

It returns the experimental DSL, report summary, warnings, output report path, and stage timings. If the task is not complete it returns `DSL_NOT_READY`; if the variant is missing it returns `M29_DIRECT_DSL_NOT_FOUND`.

The M29 direct variant may consume M29.5 replay plan evidence when present. If M29.5 fails, the direct replay path can fall back to the current M29.2 direct replay behavior, and the failed M29.5 stage remains visible in `stage_timings.json`.

If `m29_direct_replay` or `m29_direct_asset_publish` fails, the failed stage is visible in `stage_timings.json`. This does not necessarily mean the upload task failed, because M29 direct is non-blocking and the mainline M30/M38/M39 DSL can still complete.

M34.1 增加 M30 text editability diagnostics：

```text
textEditabilityDecisions
preservedGraphicTextItems
reviewTextItems
summary.editableTextCount
summary.preservedGraphicTextCount
summary.reviewTextCount
summary.textEditabilityReasonCounts
```

这些字段回答的是“这段 OCR/M29 文字证据为什么没有被物化为普通 Figma text layer”。它们不是 OCR 过滤日志，因为 OCR 证据不会在 M29 前被删除。

M34.2 extends each `textEditabilityDecisions[]` item with:

```text
metrics.preserveSignals
metrics.editableCounterSignals
```

`preserveSignals` records the negative evidence that made the text risky. `editableCounterSignals` records generic UI geometry that made the text safe enough to materialize despite weak preserve signals.

M34.3 adds M30 text-symbol leakage diagnostics:

```text
textSymbolLeakageDecisions
summary.trimmedTextSymbolLeakageCount
summary.reviewTextSymbolLeakageCount
summary.textSymbolLeakageReasonCounts
```

These fields explain when emitted editable text was cleaned because source pixels showed a leading symbol-like glyph separated from real text by a projection gap.

M36 records text foreground sampling diagnostics for emitted editable text:

```text
text node meta.textForegroundColorSource
summary.sampledTextForegroundCount
summary.defaultContrastTextForegroundCount
summary.defaultTextColorFallbackCount
```

These fields explain whether `style.color` came from source-pixel foreground sampling, contrast fallback, or hard default fallback.

M36.1 keeps these fields stable but changes the internal foreground bucket selection from largest bucket to contrast-weighted scoring. If small white badge text is rendered dark, inspect source-pixel candidates before changing OCR or text editability.

M30.6 adds accepted-image materialization diagnostics inside the existing M30 report:

```text
summary.materializedAcceptedImageCount
materializedImageNodes[].reasons includes accepted_image_low_text_overlap
materializedImageNodes[].reasons includes raw_m29_lineage_recovered
image node meta.m30AcceptedImageMaterialization = true
image node meta.sourceM29NodeIds
```

If a large product or banner image is still not draggable, first inspect `skippedItems[]` in `GET /api/tasks/{taskId}/m30-materialization`. A remaining `unsafe_text_overlap` means the item did not pass the M30.6 accepted-image gate, usually because overlap was above threshold, a high-risk flag was present, or lineage could not resolve back to a raw M29 image id.

M30.7 adds raster deduplication and composite media diagnostics inside the same M30 report:

```text
summary.materializedCompositeMediaCount
summary.cleanedMaterializedImageAssetCount
summary.erasedTextFromMaterializedImageAssetCount
summary.skippedCompositeMediaCount
materializedImageNodes[].reasons includes composite_media_block
image node meta.m30CompositeMediaMaterialization = true
```

If editable product-card text shows a ghost after dragging, inspect `cleanedMaterializedImageAssetCount` and warnings starting with `m30_image_asset_text_erasure_`. If a carousel/banner still cannot be selected, inspect `skippedItems[]` with `sourceKind=m2905_composite_media_object`; common skip reasons are `composite_media_too_small`, `missing_combined_asset_path`, `unsafe_composite_media_risk`, and `duplicate_materialized_image_bbox`.

M37 adds `m37_hierarchy_readiness` to `stage_timings.json` when M31 and M30 artifacts are available. It writes:

```text
storage/m30_1_uploads/{taskId}/m37/m37_hierarchy_readiness_report.json
```

The report is not a Renderer input. Its key guard fields are:

```text
createdVisibleFrameCount = 0
dslChanged = false
```

M38 adds `m38_hierarchy_materialization` to `stage_timings.json` when M37 exists and M38 is enabled. It writes:

```text
storage/m30_1_uploads/{taskId}/m38/hierarchy_materialization_report.json
```

The key guard fields are:

```text
absolutePositionViolationCount = 0
fallbackMovedCount = 0
originalReferenceMovedCount = 0
assetChanged = false
```

If M38 changes the DSL, the flat baseline is preserved at:

```text
storage/m30_1_uploads/{taskId}/m30/m30_materialized_dsl_flat.json
```

M39 adds `m39_boundary_classification` to `stage_timings.json`. It writes:

```text
storage/m30_1_uploads/{taskId}/m39/m39_boundary_classification_report.json
```

The report summary includes:

```text
totalClassifiedNodeCount
chromeNodeCount
contentNodeCount
onnxProposerEnabled
onnxModelLoaded
onnxCandidateCount
ruleOnlyClassificationCount
modelAssistedClassificationCount
```

The report also includes top-level `modelSkippedReason`, `warnings`, `proposedChromeBoxes`, and `classifiedNodes[]`. `modelSkippedReason` is `null` when the proposer ran or was disabled without error; expected fallback values include `missing_dependency:numpy`, `missing_dependency:PIL`, `missing_dependency:onnxruntime`, `missing_model`, `inference_failed`, and `unexpected_output_shape`.

Each classified M30 DSL node receives `meta.boundaryClassification` set to `"chrome"` or `"content"`. Per-node entries include `nodeId`, `role`, `bbox`, `classification`, `matchedRules`, `modelAssisted`, and `onnxOverlap`. If a product-card text in the center is incorrectly classified as chrome, inspect the report's per-node classification entries and verify relative geometry rule thresholds. If the ONNX model is not loaded, `onnxModelLoaded` will be `false` and all classifications are rule-only.

The read-only API endpoint is:

```text
GET /api/tasks/{taskId}/m39-boundary-classification
```

It returns task status/stage, summary, warnings, `modelSkippedReason`, classified nodes, report path, and `stage_timings.json`. If M39 is disabled or the report is missing, it returns `M39_BOUNDARY_CLASSIFICATION_NOT_FOUND`.

M39.1 adds `m39_1_unit_structure_readiness_audit` to `stage_timings.json` when M31 artifacts exist and the stage is enabled. It writes:

```text
storage/m30_1_uploads/{taskId}/m39_1/unit_structure_readiness_report.json
```

The report summary includes:

```text
m30NodeCount
m31UnitCount
m37SafeUnitCount
m38CreatedContainerCount
candidateUnitCount
readyCandidateCount
blockedCandidateCount
microCandidateCount
chromeShellCandidateCount
contentSectionCandidateCount
productCardCandidateCount
bannerCandidateCount
onnxModelLoaded
onnxCandidateCount
dslChanged = false
createdVisibleNodeCount = 0
assetChanged = false
```

`candidateUnits[]` explains existing safe M37 units, blocked/micro units, geometry-derived product-card/banner candidates, boundary-derived chrome/content candidates, and diagnostic ONNX boxes. `blockerSummary` aggregates reasons such as `micro_unit_only`, `insufficient_direct_matches`, `lineage_gap`, `boundary_classification_conflict`, `duplicate_unit_bbox`, `unsupported_visual_kind`, `model_only_untrusted`, and `overlaps_existing_safe_unit`.

The read-only API endpoint is:

```text
GET /api/tasks/{taskId}/m39-1-unit-structure-readiness
```

It returns task status/stage, summary, warnings, `modelSkippedReason`, candidate units, promotion hints, report path, and `stage_timings.json`. If M39.1 is disabled or the report is missing, it returns `M39_1_UNIT_STRUCTURE_READINESS_NOT_FOUND`.

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

M8 primitive result 至少包含：

- `taskId`
- `provider`
- `model`
- `status`
- `primitiveCount`
- `relationCount`
- `errorCode`
- `primitivePath`

M10 OCR/patch result 至少包含：

- `taskId`
- `provider` 或 `mode`
- `status`
- `blockCount`
- `patchCount`
- `warningCount`
- `errorCode`
- `ocrPath`
- `patchPath`

百度 PP-OCRv5 provider 的 OCR JSON `meta` 还应包含远端 `jobId`、提交耗时、轮询耗时、轮询次数和低置信度过滤数量，方便定位远端耗时和质量问题。

M14 text replacement result 至少包含：

- `taskId`
- `mode`
- `status`
- `acceptedCount`
- `rejectedCount`
- `appliedCount`
- `blockedAcceptedCount`
- risk summary
- region summary
- reason summary
- sampling strategy summary
- rescued from complex background count
- `warningCount`
- `errorCode`
- `replacementPath`

M15 text binding result 至少包含：

- `taskId`
- `status`
- `containerCount`
- `bindingCount`
- `unboundCount`
- role summary
- relationship summary
- `warningCount`
- `errorCode`
- `bindingPath`

M16 component structure result 至少包含：

- `taskId`
- `status`
- `componentCount`
- `groupCount`
- `unstructuredCount`
- component role summary
- group role summary
- layout summary
- `warningCount`
- `errorCode`
- `structurePath`

M17 component annotation result 至少包含：

- `taskId`
- `status`
- `annotationCount`
- `annotatedElementCount`
- `unannotatedElementCount`
- `groupHintCount`
- component role summary
- unresolved component count
- `warningCount`
- `errorCode`
- `annotationPath`

M18 layer separation result 至少包含：

- `taskId`
- `status`
- `candidateCount`
- `fillCandidateCount`
- `repairRequiredCount`
- `embeddedTextCount`
- `blockedCount`
- strategy summary
- risk summary
- fallback context count
- `warningCount`
- `errorCode`
- `separationPath`

M19 asset slice result 至少包含：

- `taskId`
- `status`
- `sliceCount`
- `filledSliceCount`
- `blockedCount`
- `failedSliceCount`
- role summary
- strategy summary
- `warningCount`
- `errorCode`
- `slicePath`

M20 icon candidate result 至少包含：

- `taskId`
- `status`
- `iconCount`
- `croppedIconCount`
- `blockedCount`
- `failedCropCount`
- source summary
- role summary
- `warningCount`
- `errorCode`
- `iconPath`

M21 icon coverage audit result 至少包含：

- `taskId`
- `status`
- `placementCount`
- `missedIconHintCount`
- `readyCount`
- `needsFallbackCoordinationCount`
- `needsSliceCoordinationCount`
- `blockedCount`
- coverage by source
- missed hint by source
- `overlayAssetId`
- `warningCount`
- `errorCode`
- `auditPath`

M22 icon gap candidate result 至少包含：

- `taskId`
- `status`
- `gapIconCount`
- `croppedGapIconCount`
- `blockedCount`
- `failedCropCount`
- source summary
- blocked reason summary
- `overlayAssetId`
- `warningCount`
- `errorCode`
- `gapPath`

M23 icon placement plan result 至少包含：

- `taskId`
- `status`
- `placementCount`
- `readyCount`
- `needsFallbackMaskCount`
- `needsSliceCoordinationCount`
- `needsFallbackCoordinationCount`
- `reviewRequiredCount`
- `blockedCount`
- `dedupedCount`
- decision summary
- role summary
- `overlayAssetId`
- `warningCount`
- `errorCode`
- `planPath`

M24 visible icon fallback result 至少包含：

- `taskId`
- `status`
- `selectedCount`
- `appliedCount`
- `blockedCount`
- `skippedCount`
- role summary
- blocked reason summary
- `overlayAssetId`
- `warningCount`
- `errorCode`
- `fallbackPath`

M25 business icon candidate result 至少包含：

- `taskId`
- `status`
- `businessIconCount`
- `croppedBusinessIconCount`
- `blockedCount`
- `failedCropCount`
- source summary
- blocked reason summary
- `overlayAssetId`
- `warningCount`
- `errorCode`
- `businessPath`

M26 perception benchmark result 至少包含：

- `taskId`
- `status`
- `providerCount`
- `candidateCount`
- `blockedCount`
- `recommendedProvider`
- `elapsedMs`
- per-provider `elapsedMs`
- per-provider candidate/blocked/duplicate/text overlap/background/small stroke 数量
- likely hit proxy counts: bottom nav、button arrow、card tile、room status
- `rulesOverlayAssetId`
- `opencvOverlayAssetId`
- `sam2OverlayAssetId`
- `uiedOverlayAssetId`
- `warningCount`
- `errorCode`
- `benchmarkPath`

## Metrics

开发阶段优先从日志中观察：

- 上传耗时。
- OCR 耗时。
- AI 调用耗时。
- primitive extraction 成功/失败数量。
- DSL patch build 成功/失败数量。
- text replacement accepted/rejected/applied/blocked/rescued 数量。
- text replacement strategy 命中分布。
- text binding bound/unbound/container 数量。
- text binding role/relationship 分布。
- component structure component/group/unstructured 数量。
- component structure role/group/layout 分布。
- component annotation annotated/unannotated/group hint 数量。
- component annotation role 分布和 unresolved component 数量。
- layer separation candidate/fill/repair/embedded/blocked 数量。
- layer separation strategy/risk 分布。
- asset slice original/filled/blocked/failed 数量。
- icon candidate/cropped/blocked/failed 数量。
- icon candidate source/role 分布。
- icon coverage placement/missed hint/ready/coordination/blocked 数量。
- icon coverage source/hint 分布。
- icon gap candidate/cropped/blocked/failed 数量。
- icon gap source/blocked reason 分布。
- icon placement plan ready/fallback-mask/slice/blocked/deduped 数量。
- icon visible fallback selected/applied/blocked/skipped 数量。
- business icon candidate/cropped/blocked/failed 数量。
- business icon source/blocked reason 分布。
- perception benchmark provider/candidate/blocked 数量。
- perception benchmark provider 耗时和 recommended provider。
- perception benchmark likely hit 与误检代理指标。
- SAM visual raw mask/candidate/blocked 数量。
- SAM visual elapsedMs、kind summary 和 blocked reason summary。
- DSL 生成耗时。
- 资产裁切耗时。
- Renderer 渲染耗时。
- 成功/失败数量。

不接入复杂 metrics 平台。

## Traces

v0.1 不做分布式 trace。

任务内用 `taskId` 串起：

```text
upload -> preprocess -> asset_crop -> primitive_extract -> ocr_extract -> dsl_patch_build -> text_replacement -> text_binding -> component_structure -> component_annotation -> layer_separation -> asset_slice -> icon_candidate -> icon_coverage_audit -> icon_gap_candidate -> icon_placement_plan -> icon_visible_fallback -> icon_business_candidate -> perception_benchmark -> sam_visual_candidate -> dsl_validate
```

插件渲染阶段用 `taskId` 和 DSL `version` 关联。

## Debug Artifacts

建议保留：

- 原始 PNG。
- 预处理结果。
- OCR 摘要。
- AI 输出摘要。
- visual primitive JSON。
- OCR JSON。
- DSL patch JSON。
- text replacement JSON。
- text binding JSON。
- component structure JSON。
- component annotation JSON。
- layer separation candidate JSON。
- asset slice candidate JSON。
- icon candidate JSON。
- icon coverage audit JSON。
- icon coverage overlay PNG。
- icon gap candidate JSON。
- icon gap overlay PNG。
- icon placement plan JSON。
- icon placement overlay PNG。
- icon visible fallback JSON。
- icon visible fallback overlay PNG。
- icon business candidate JSON。
- icon business overlay PNG。
- perception benchmark JSON。
- perception benchmark provider overlay PNG。
- SAM visual candidate JSON。
- SAM visual candidate overlay PNG。
- DSL 文件。
- 资产 metadata。
- Renderer warning。

不默认保存完整模型输入输出，避免隐私和成本问题。
