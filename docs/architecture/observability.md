# 可观测性

v0.1 只做能定位问题的日志，不做完整监控平台。

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
- DSL 生成耗时。
- 资产裁切耗时。
- Renderer 渲染耗时。
- 成功/失败数量。

不接入复杂 metrics 平台。

## Traces

v0.1 不做分布式 trace。

任务内用 `taskId` 串起：

```text
upload -> preprocess -> asset_crop -> primitive_extract -> ocr_extract -> dsl_patch_build -> text_replacement -> text_binding -> component_structure -> component_annotation -> layer_separation -> asset_slice -> icon_candidate -> icon_coverage_audit -> icon_gap_candidate -> icon_placement_plan -> dsl_validate
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
- DSL 文件。
- 资产 metadata。
- Renderer warning。

不默认保存完整模型输入输出，避免隐私和成本问题。
