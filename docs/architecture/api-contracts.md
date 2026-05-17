# API Contracts

API v0.1 只服务单张 PNG -> DSL -> Figma 主链路。

## Contract Ownership

API 合同由后端和 Figma 插件共同遵守。任何接口路径、请求体、响应结构、错误码、任务状态变更，必须同步更新本文档和相关实现计划。

## Base URL

开发环境默认：

```text
http://localhost:8000/api
```

## Response Shape

成功：

```json
{
  "success": true,
  "data": {}
}
```

失败：

```json
{
  "success": false,
  "error": {
    "code": "UPLOAD_FAILED",
    "message": "图片上传失败，请检查网络后重试。",
    "detail": "Internal debug detail",
    "stage": "upload",
    "taskId": "task_001"
  }
}
```

## Required Endpoints

`GET /api/health`

- 用途：确认后端服务运行。
- 返回：`status`、`version`、`time`。

`POST /api/upload`

- 用途：上传 PNG 并创建任务。
- 请求：multipart file。
- M24 成功后立即返回 completed deterministic region + hidden OCR candidate 任务；默认 text replacement debug 不改变可见 DSL。
- 成功返回：`taskId`、文件信息、状态、阶段和进度。
- 必须拒绝非 PNG、无法读取尺寸的 PNG 和过大图片。
- 默认大小上限：10MB。
- 返回 DSL 时，portrait/mobile-like PNG 默认包含 `fallback_region_header`、`fallback_region_content`、`fallback_region_bottom` 三个 region fallback。
- 如果 cropper 不支持该 PNG 格式，任务仍可 completed，DSL 退回整图 fallback 并带 `qualityFlags`。
- 上传链路会生成 visual primitives、OCR、DSL patch、text replacement、text binding、component structure、component annotation、layer separation candidate、asset slice candidate、icon candidate、icon coverage audit、icon gap candidate 和 icon placement plan 调试结果。默认 `DSL_PATCH_MODE=debug` 会在 DSL 中加入 hidden text candidates；默认 `TEXT_REPLACEMENT_MODE=debug` 只保存 replacement decisions，不改变 Figma 可见输出。显式设置 `TEXT_REPLACEMENT_MODE=apply` 后应用 accepted 且通过 quality gate 的文字替换；M14 会在 quality gate 前记录 UI-aware sampling strategy。M15 默认生成 text binding 报告，把 OCR/replacement text 绑定到 visual primitives 或 inferred UI containers；M16 默认生成 component structure 报告，把 M15 containers/bindings 聚合成 component candidates 和 layout groups；M17 默认生成 component annotation 报告，并只把 M16 结构挂到已有 DSL element 的 `name`/`meta`；M18 默认生成 layer separation candidate 报告，并只追加 DSL 顶层 meta；M19 默认生成本地 asset slice candidate 报告和实验 PNG，并只追加 DSL 顶层 meta；M20 默认生成 icon candidate 报告和 icon PNG，并只追加 DSL 顶层 meta；M21 默认生成 icon coverage audit 报告和 debug overlay，并只追加 DSL 顶层 meta；M22 默认生成 region-guided icon gap candidate 报告、gap icon PNG 和 debug overlay，并只追加 DSL 顶层 meta；M23 默认生成 icon placement plan 报告和 debug overlay，并只追加 DSL 顶层 meta。M15-M23 都不改变 Figma 可见输出。M24 默认关闭；显式设置 `ICON_VISIBLE_FALLBACK_ENABLED=true` 后才会追加 `icon_fallback_cover` 和 `visible_icon_fallback` 可见节点，并追加实际使用的 icon asset 到 DSL `assets`。

`GET /api/tasks/{taskId}`

- 用途：查询任务状态。
- 返回：`taskId`、`status`、`stage`、`progress`、`message`。

`GET /api/tasks/{taskId}/dsl`

- 用途：获取任务 DSL。
- 仅在任务 completed 后成功。
- 未完成时返回明确错误。
- 默认 `DSL_PATCH_MODE=debug` 时返回 enhanced DSL，包含 hidden `candidate_text`。
- `DSL_PATCH_MODE=off` 时返回 M7 base DSL。
- patch build 或 validation 失败时返回 base DSL。
- `TEXT_REPLACEMENT_MODE=apply` 时可额外包含 `text_replacement_cover` 和 `visible_text_replacement`；只有通过 M13/M14 decision 和 quality gate 的 replacement 会进入 DSL，replacement 失败时回退 M10/M9 输出。
- M15 只更新 DSL `meta`：`qualityFlags` 可追加 `m15_text_primitive_binding`，并写入 `textPrimitiveBindingCount`、`textPrimitiveContainerCount`、`textPrimitiveUnboundCount`。M15 不新增可见 DSL 节点。
- M16 只更新 DSL `meta`：`qualityFlags` 可追加 `m16_component_structure_harness`，并写入 `componentStructureCount`、`componentStructureGroupCount`、`componentStructureUnstructuredCount`。M16 不新增可见 DSL 节点。
- M17 只更新已有 DSL element 的 `name`/`meta` 和 DSL 顶层 `meta`：`qualityFlags` 可追加 `m17_component_annotation`，并写入 `componentAnnotationCount`、`componentAnnotatedElementCount`、`componentUnannotatedElementCount`、`componentGroupHintCount`。M17 不新增可见 DSL 节点，不改 layout/style/content/source/imageFill/visible。
- M18 只更新 DSL 顶层 `meta`：`qualityFlags` 可追加 `m18_layer_separation_candidates`，并写入 `layerSeparationCandidateCount`、`layerSeparationFillCandidateCount`、`layerSeparationRepairRequiredCount`、`layerSeparationEmbeddedTextCount`、`layerSeparationBlockedCount`。M18 不新增可见 DSL 节点，不改任何已有 element 的 name/meta/layout/style/content/source/imageFill/visible/children。
- M19 只更新 DSL 顶层 `meta`：`qualityFlags` 可追加 `m19_local_asset_slice_candidates`，并写入 `assetSliceCandidateCount`、`assetSliceFilledCandidateCount`、`assetSliceBlockedCount`、`assetSliceFailedCount`。M19 不新增可见 DSL 节点，不改任何已有 element，也不修改 DSL `assets` 数组。
- M20 只更新 DSL 顶层 `meta`：`qualityFlags` 可追加 `m20_icon_candidate_extraction`，并写入 `iconCandidateCount`、`iconCroppedAssetCount`、`iconBlockedCount`、`iconFailedCropCount`。M20 不新增可见 DSL 节点，不改任何已有 element，也不修改 DSL `assets` 数组。
- M21 只更新 DSL 顶层 `meta`：`qualityFlags` 可追加 `m21_icon_coverage_audit`，并写入 `iconCoverageCandidateCount`、`iconCoveragePlacementCount`、`iconCoverageMissedHintCount`、`iconPlacementReadyCount`、`iconPlacementNeedsFallbackCoordinationCount`、`iconPlacementNeedsSliceCoordinationCount`、`iconPlacementBlockedCount`。M21 不新增可见 DSL 节点，不改任何已有 element，也不修改 DSL `assets` 数组。
- M22 只更新 DSL 顶层 `meta`：`qualityFlags` 可追加 `m22_icon_gap_candidates`，并写入 `iconGapCandidateCount`、`iconGapCroppedAssetCount`、`iconGapBlockedCount`、`iconGapFailedCropCount`。M22 不新增可见 DSL 节点，不改任何已有 element，也不修改 DSL `assets` 数组。
- M23 只更新 DSL 顶层 `meta`：`qualityFlags` 可追加 `m23_icon_placement_plan`，并写入 `iconPlacementPlanCount`、`iconPlacementReadyCount`、`iconPlacementNeedsFallbackMaskCount`、`iconPlacementNeedsSliceCoordinationCount`、`iconPlacementNeedsFallbackCoordinationCount`、`iconPlacementReviewRequiredCount`、`iconPlacementBlockedCount`、`iconPlacementDedupedCount`。M23 不新增可见 DSL 节点，不改任何已有 element，也不修改 DSL `assets` 数组。
- M24 默认不生成 result、不修改 DSL。开启 `ICON_VISIBLE_FALLBACK_ENABLED=true` 后，DSL 顶层 `meta` 可追加 `m24_visible_icon_fallback_replay`，并写入 `visibleIconFallbackSelectedCount`、`visibleIconFallbackAppliedCount`、`visibleIconFallbackBlockedCount`、`visibleIconFallbackSkippedCount`。M24 只能 append 实际使用的 icon asset、`icon_fallback_cover` shape 和 `visible_icon_fallback` image node，不能修改任何已有 element 或已有 asset。

`GET /api/tasks/{taskId}/primitives`

- 用途：获取 M8 visual primitive candidate 结果。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- primitive result 不存在返回 `PRIMITIVE_NOT_FOUND`。
- extraction 失败时仍返回 `success: true`，但 `data.status` 为 `failed`，并带 `error` 摘要。
- 返回的 `bbox` 使用整图像素坐标 `[x, y, width, height]`。

`GET /api/tasks/{taskId}/ocr`

- 用途：获取 OCR candidate 结果。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- OCR result 不存在返回 `OCR_NOT_FOUND`。
- OCR failed 时仍返回 `success: true`，但 `data.status` 为 `failed`，并带 `error`。
- 返回的 `bbox` 使用整图像素坐标 `[x, y, width, height]`。

`GET /api/tasks/{taskId}/dsl-patch`

- 用途：获取 DSL patch 结果。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- patch result 不存在返回 `DSL_PATCH_NOT_FOUND`。
- patch failed 时仍返回 `success: true`，但 `data.status` 为 `failed`，并带 `error`。
- M9 patch 只允许添加 hidden `candidate_text`。

`GET /api/tasks/{taskId}/text-replacements`

- 用途：获取 M14 visible text replacement decisions、sampling strategy 和质量门禁结果。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- replacement result 不存在返回 `TEXT_REPLACEMENT_NOT_FOUND`。
- replacement failed/skipped 时仍返回 `success: true`，但 `data.status` 为 `failed`/`skipped`，并带 `error`。
- decisions 可包含 `background`、`foreground`、`sourceOcrBlockIds`、`strategy`、`quality` 和 `application` 调试字段，用于解释彩色背景替换、OCR block 合并、UI-aware sampling、风险等级和 apply 阻断原因。

`GET /api/tasks/{taskId}/text-bindings`

- 用途：获取 M15 text-to-container binding 报告。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- binding result 不存在返回 `TEXT_BINDING_NOT_FOUND`。
- binding failed/skipped 时仍返回 `success: true`，但 `data.status` 为 `failed`/`skipped`，并带 `error`。
- 返回 `containers`、`bindings`、`unboundTextIds`、`warnings` 和 `meta`。`containers` 可包含 `source=visual_primitive`、`source=inferred_from_text_cluster` 或 `source=fallback_region`。

`GET /api/tasks/{taskId}/component-structures`

- 用途：获取 M16 component structure 报告。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- structure result 不存在或文件缺失返回 `COMPONENT_STRUCTURE_NOT_FOUND`。
- structure failed/skipped 时仍返回 `success: true`，但 `data.status` 为 `failed`/`skipped`，并带 `error`。
- 返回 `components`、`groups`、`unstructuredContainerIds`、`warnings` 和 `meta`。`components` 聚合 M15 container/binding facts；`groups` 描述 summary stat row、shortcut grid、preview section、bottom nav row 和 page structure 等布局候选。

`GET /api/tasks/{taskId}/component-annotations`

- 用途：获取 M17 DSL component annotation 和 layer naming 报告。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- annotation result 不存在或文件缺失返回 `COMPONENT_ANNOTATION_NOT_FOUND`。
- annotation failed/skipped 时仍返回 `success: true`，但 `data.status` 为 `failed`/`skipped`，并带 `error`。
- 返回 `annotations`、`groupHints`、`unannotatedElementIds`、`unresolvedComponentIds`、`warnings` 和 `meta`。`annotations` 只描述已有 DSL element 与 M16 component/group 的确定性 ID join；`groupHints` 只是 future grouping hint，不会让 Renderer 创建真实 Figma group。

`GET /api/tasks/{taskId}/layer-separation-candidates`

- 用途：获取 M18 component-aware layer separation candidate 报告。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- result 不存在或文件缺失返回 `LAYER_SEPARATION_NOT_FOUND`。
- separation failed/skipped 时仍返回 `success: true`，但 `data.status` 为 `failed`/`skipped`，并带 `error`。
- 返回 `candidates`、`fallbackContexts`、`blockedComponentIds`、`warnings` 和 `meta`。`candidates` 只描述后续是否适合 shape + editable text、image slice with simple fill candidate、future repair、embedded text 或 no text；不会让 Renderer 切图、删除 fallback 或创建真实 Figma group/component。

`GET /api/tasks/{taskId}/asset-slice-candidates`

- 用途：获取 M19 local asset slice/simple fill experiment 报告。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- result 不存在或文件缺失返回 `ASSET_SLICE_NOT_FOUND`。
- slice failed/skipped 时仍返回 `success: true`，但 `data.status` 为 `failed`/`skipped`，并带 `error`。
- 返回 `slices`、`blockedComponentIds`、`warnings` 和 `meta`。`slices` 可包含 original slice PNG 和 filled slice PNG URL，但这些实验资产不会写入 DSL `assets`，不会让 Renderer 替换 fallback。

`GET /api/tasks/{taskId}/icon-candidates`

- 用途：获取 M20 icon candidate extraction/crop 报告。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- result 不存在或文件缺失返回 `ICON_CANDIDATE_NOT_FOUND`。
- icon candidate failed/skipped 时仍返回 `success: true`，但 `data.status` 为 `failed`/`skipped`，并带 `error`。
- 返回 `icons`、`blockedComponentIds`、`warnings` 和 `meta`。`icons` 可包含 icon PNG URL，但这些候选资产不会写入 DSL `assets`，不会让 Renderer 创建可见 icon 节点。

`GET /api/tasks/{taskId}/icon-coverage-audit`

- 用途：获取 M21 icon coverage audit 和 placement readiness 报告。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- result 不存在或文件缺失返回 `ICON_COVERAGE_AUDIT_NOT_FOUND`。
- audit failed/skipped 时仍返回 `success: true`，但 `data.status` 为 `failed`/`skipped`，并带 `error`。
- 返回 `placements`、`missedIconHints`、`coverageOverlay`、`blockedIconCandidateIds`、`warnings` 和 `meta`。`coverageOverlay` 可包含 debug overlay PNG URL，但 overlay 不会写入 DSL `assets`，不会让 Renderer 创建可见节点。

`GET /api/tasks/{taskId}/icon-gap-candidates`

- 用途：获取 M22 region-guided icon gap candidate 报告。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- result 不存在或文件缺失返回 `ICON_GAP_CANDIDATE_NOT_FOUND`。
- gap candidate failed/skipped 时仍返回 `success: true`，但 `data.status` 为 `failed`/`skipped`，并带 `error`。
- 返回 `gapIcons`、`blockedHints`、`gapOverlay`、`warnings` 和 `meta`。`gapIcons` 可包含 gap icon PNG URL，`gapOverlay` 可包含 debug overlay PNG URL；二者都不会写入 DSL `assets`，不会让 Renderer 创建可见节点。

`GET /api/tasks/{taskId}/icon-placement-plan`

- 用途：获取 M23 icon placement plan 和 layering readiness 报告。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- result 不存在或文件缺失返回 `ICON_PLACEMENT_PLAN_NOT_FOUND`。
- placement plan failed/skipped 时仍返回 `success: true`，但 `data.status` 为 `failed`/`skipped`，并带 `error`。
- 返回 `placements`、`dedupedIcons`、`blockedIcons`、`placementOverlay`、`warnings` 和 `meta`。`futureDslNodeHint` 只存在于 report，不写入 DSL；`placementOverlay` 不写入 DSL `assets`，不会让 Renderer 创建可见节点。

`GET /api/tasks/{taskId}/icon-visible-fallback`

- 用途：获取 M24 visible icon fallback replay experiment 报告。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- result 不存在或文件缺失返回 `ICON_VISIBLE_FALLBACK_NOT_FOUND`。
- visible fallback failed/skipped 时仍返回 `success: true`，但 `data.status` 为 `failed`/`skipped`，并带 `error`。
- 返回 `visibleIcons`、`blockedPlacements`、`visibleFallbackOverlay`、`warnings` 和 `meta`。默认 `ICON_VISIBLE_FALLBACK_ENABLED=false` 时不生成 result。开启后，`visibleIcons` 对应最终 DSL 中新增的 `icon_fallback_cover` 和 `visible_icon_fallback` 节点。

`GET /api/assets/{assetId}`

- 用途：获取资产信息或文件访问。
- 后端返回资产元信息，不直接返回文件 bytes。
- 开发阶段 URL 指向 `/files/uploads/...` 或 `/files/assets/...`。
- 如果多个任务有同名 `assetId`，当前返回最新匹配资产。后续再决定是否引入 task-scoped asset API。

## Static Files

后端挂载：

```text
/files/uploads
/files/assets
```

DSL 中的 asset URL 指向这些路径，方便 Figma Renderer 直接 fetch 图片。

## Error Codes

- `INVALID_FILE_TYPE`
- `INVALID_IMAGE_DIMENSIONS`
- `FILE_TOO_LARGE`
- `UPLOAD_FAILED`
- `TASK_NOT_FOUND`
- `DSL_NOT_READY`
- `DSL_NOT_FOUND`
- `ASSET_NOT_FOUND`
- `PRIMITIVE_NOT_FOUND`
- `PRIMITIVE_EXTRACTION_FAILED`
- `OCR_NOT_FOUND`
- `OCR_EXTRACTION_FAILED`
- `DSL_PATCH_NOT_FOUND`
- `DSL_PATCH_BUILD_FAILED`
- `DSL_PATCH_VALIDATION_FAILED`
- `TEXT_REPLACEMENT_NOT_FOUND`
- `TEXT_REPLACEMENT_FAILED`
- `TEXT_REPLACEMENT_VALIDATION_FAILED`
- `TEXT_BINDING_NOT_FOUND`
- `TEXT_BINDING_FAILED`
- `TEXT_BINDING_VALIDATION_FAILED`
- `COMPONENT_STRUCTURE_NOT_FOUND`
- `COMPONENT_STRUCTURE_FAILED`
- `COMPONENT_STRUCTURE_VALIDATION_FAILED`
- `COMPONENT_ANNOTATION_NOT_FOUND`
- `COMPONENT_ANNOTATION_FAILED`
- `COMPONENT_ANNOTATION_VALIDATION_FAILED`
- `LAYER_SEPARATION_NOT_FOUND`
- `LAYER_SEPARATION_FAILED`
- `LAYER_SEPARATION_VALIDATION_FAILED`
- `ASSET_SLICE_NOT_FOUND`
- `ASSET_SLICE_FAILED`
- `ASSET_SLICE_VALIDATION_FAILED`
- `ICON_CANDIDATE_NOT_FOUND`
- `ICON_CANDIDATE_FAILED`
- `ICON_CANDIDATE_VALIDATION_FAILED`
- `ICON_COVERAGE_AUDIT_NOT_FOUND`
- `ICON_COVERAGE_AUDIT_FAILED`
- `ICON_COVERAGE_AUDIT_VALIDATION_FAILED`
- `ICON_GAP_CANDIDATE_NOT_FOUND`
- `ICON_GAP_CANDIDATE_FAILED`
- `ICON_GAP_CANDIDATE_VALIDATION_FAILED`
- `ICON_PLACEMENT_PLAN_NOT_FOUND`
- `ICON_PLACEMENT_PLAN_FAILED`
- `ICON_PLACEMENT_PLAN_VALIDATION_FAILED`
- `ICON_VISIBLE_FALLBACK_NOT_FOUND`
- `ICON_VISIBLE_FALLBACK_FAILED`
- `ICON_VISIBLE_FALLBACK_VALIDATION_FAILED`
- `INTERNAL_ERROR`

## Plugin M5 Usage

M5 插件使用：

```text
POST /api/upload
GET /api/tasks/{taskId}
GET /api/tasks/{taskId}/dsl
```

即使后端当前立即返回 `completed`，插件仍按 task 查询流程实现，避免后续接真实异步处理时重写主链路。

M24 仍不改插件调用路径。插件不调用 OCR、primitives、dsl-patch、text-replacements、text-bindings、component-structures、component-annotations、layer-separation-candidates、asset-slice-candidates、icon-candidates、icon-coverage-audit、icon-gap-candidates、icon-placement-plan 或 icon-visible-fallback endpoint。

## Optional Endpoints

以下接口不进入 P0：

- `POST /api/tasks/{taskId}/retry`
- `GET /api/tasks/{taskId}/logs`

## Contract Change Rules

- 不兼容字段变更必须升级 DSL 或 API 版本。
- 不允许插件依赖未文档化字段。
- 不允许后端返回未校验 DSL。
- 错误必须包含稳定 `code`。
- 普通用户文案和开发 detail 要分层。
