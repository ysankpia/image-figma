# DSL v0.1

DSL v0.1 是后端识别管线和 Figma Renderer 之间的稳定合同。

## Contract Role

后端负责：

```text
PNG -> OCR / AI / CV -> DSL v0.1
```

Renderer 负责：

```text
DSL v0.1 -> Figma Nodes
```

任何未通过校验的 DSL 不应直接进入 Renderer。

## Top-Level Shape

DSL 顶层必须包含：

- `version`：固定为 `"0.1"`。
- `taskId`：任务 ID。
- `page`：页面尺寸、背景、安全区等。
- `assets`：图片资产数组。
- `root`：根元素。
- `meta`：可选调试和来源信息。

## Element Types

v0.1 元素类型只支持：

- `frame`
- `group`
- `text`
- `shape`
- `image`
- `icon`
- `line`

基础元素必须有：

- `id`
- `type`
- `layout`

可选字段：

- `role`
- `name`
- `rawLayout`
- `style`
- `content`
- `source`
- `imageFill`
- `children`
- `meta`

## Layout Rule

v0.1 使用绝对定位优先：

- `x`
- `y`
- `width`
- `height`

不在 v0.1 中推断 Auto Layout、响应式约束、Hug Content、Fill Container。

原因：输入是 PNG，系统无法可靠知道真实布局意图。

## Style Scope

v0.1 支持基础视觉样式：

- fill。
- stroke。
- radius。
- shadow。
- opacity。
- visible。
- text style。
- image fill mode。

复杂渐变、复杂 mask、复杂图表、复杂多色图标可以 fallback。

## Fallback

Fallback 是设计策略，不是失败。

以下内容允许 fallback 为图片：

- 复杂 Banner。
- 复杂插图。
- 复杂运营图。
- 复杂图表。
- 复杂多色图标。
- 不规则 mask。
- 低置信度局部区域。

Fallback 元素必须记录原因：

```json
{
  "meta": {
    "fallback": true,
    "reason": "complex_banner",
    "confidence": 0.52
  }
}
```

M7 deterministic region DSL 默认使用三段 region fallback：

- `original_ref`：隐藏原图参考层。
- `fallback_region_header`：顶部可见 fallback。
- `fallback_region_content`：中部可见 fallback。
- `fallback_region_bottom`：底部可见 fallback。
- `meta.notes`：`deterministic_region_dsl`。

每个 region fallback 必须记录来源区域：

```json
{
  "meta": {
    "fallback": true,
    "reason": "m7_deterministic_region",
    "confidence": 1,
    "sourceBBox": [0, 234, 941, 1237]
  }
}
```

如果 PNG 可读尺寸但 cropper 不支持该格式，DSL 退回 M6 整图 fallback：

- `fallback_full_image`：可见整图 fallback。
- `meta.notes`：`deterministic_fallback_dsl`。
- `meta.qualityFlags`：包含 `region_crop_unsupported`。

M8 不识别文字、图标或真实布局。M8 新增的是独立 visual primitive candidate 结果，不会合并进 DSL。

M9 新增 OCR/DSL patch harness。默认 `/api/tasks/{taskId}/dsl` 会包含 hidden `candidate_text`：

- `type: "text"`。
- `role: "candidate_text"`。
- `style.visible: false`。
- `meta.source: "ocr"`。
- `meta.candidate: true`。
- `meta.reason: "m9_ocr_candidate_hidden_by_default"`。

这些 text candidates 是调试和 M12 可见替换的输入，不代表已经完成可编辑还原。fallback region 不删除、不移动。

M12 在 `TEXT_REPLACEMENT_MODE=apply` 时可追加 `text_replacement_cover` shape 和 `visible_text_replacement` text。它处理低复杂度背景上的 accepted OCR block，支持浅底深字、部分彩色/深色底浅字和保守 block 合并，仍保留 hidden candidate text 和 fallback region。

M13 在 M12 decision 后增加 quality gate。`decision=accepted` 且非 high-risk 的 replacement 会进入 DSL；high-risk accepted decision 只保留在 `/text-replacements` 报告里。DSL meta 可包含 `m13_text_replacement_quality_control`、`textReplacementAppliedCount` 和 `textReplacementBlockedCount`。

M14 在 M13 quality gate 前增加 UI-aware sampling。它不改变 DSL 节点形状，只让更多安全的 OCR text candidate 从 `complex_background` 误杀中进入 accepted replacement。`TEXT_REPLACEMENT_MODE=apply` 时仍追加同样的 `text_replacement_cover` shape 和 `visible_text_replacement` text，并在 DSL meta 中可记录 `m14_ui_aware_text_sampling` 和 `textReplacementRescuedCount`。fallback region、hidden candidate text 和 original reference 仍保留。

M15 新增 text-primitive binding harness。它生成独立 `/text-bindings` 报告，把 OCR/replacement text 绑定到 visual primitives 或 inferred UI containers。容器角色可覆盖 page header、hero profile、activity card、summary stat card、primary/outline button、shortcut/preview/tip card、legend group 和 bottom nav item。M15 不新增可见 DSL 节点，不重组图层；DSL meta 只记录 `m15_text_primitive_binding`、`textPrimitiveBindingCount`、`textPrimitiveContainerCount` 和 `textPrimitiveUnboundCount`。

M16 新增 component structure harness。它生成独立 `/component-structures` 报告，把 M15 containers/bindings 聚合成 component candidates 和 layout groups。component role 可覆盖 page header、hero profile、badge/status badge、activity card、summary stat card、primary/outline button、shortcut/preview/tip card、legend group、bottom nav 和 bottom nav item；group role 可覆盖 summary stat group、shortcut grid、preview section、bottom nav group 和 page structure。M16 不新增可见 DSL 节点，不创建 Figma Component/Instance，不删除 fallback region；DSL meta 只记录 `m16_component_structure_harness`、`componentStructureCount`、`componentStructureGroupCount` 和 `componentStructureUnstructuredCount`。

M17 新增 component annotation harness。它生成独立 `/component-annotations` 报告，把 M16 component/group 结构通过确定性 ID join 挂回已有 DSL element。M17 只允许修改已有 element 的 `name` 和 `meta`，不新增可见节点，不改 `layout`、`style`、`content`、`source`、`imageFill` 或 `visible`。Renderer 已使用 `element.name` 给 Figma node 命名，所以 M17 layer naming 不需要改 Renderer 协议。

M17 element meta 只追加 annotation 字段，不覆盖旧 `meta.source`、`meta.reason`、`meta.candidate` 或 `meta.fallback`：

```json
{
  "meta": {
    "componentId": "component_primary_button_001",
    "componentRole": "primary_button",
    "groupIds": ["group_page_structure_001"],
    "bindingId": "binding_016",
    "ocrBlockId": "ocr_text_016",
    "relationship": "button_label",
    "annotationSource": "m17_component_annotation"
  }
}
```

fallback region 只作为上下文 annotation，不绑定业务 component：

```json
{
  "meta": {
    "fallback": true,
    "annotationRole": "fallback_context",
    "groupIds": ["group_page_structure_001"],
    "annotationSource": "m17_component_annotation"
  }
}
```

DSL meta 可记录 `m17_component_annotation`、`componentAnnotationCount`、`componentAnnotatedElementCount`、`componentUnannotatedElementCount` 和 `componentGroupHintCount`。M17 不切图，不做图标、圆形、三角形、五角星或复杂图形识别，不删除 fallback region，不创建真实 Figma group、Component/Instance 或 Auto Layout。

M18 新增 layer separation candidate harness。它生成独立 `/layer-separation-candidates` 报告，基于 M14 replacement、M15 binding、M16 component structure 和 M17 annotation 判断每个 component 后续是否适合 shape + editable text、image slice with simple fill candidate、future repair、embedded text 或 no text。M18 第一版只输出 `solid_color_fill` simple fill candidate，不生成实际 PNG。

M18 只允许修改 DSL 顶层 `meta`：

```json
{
  "meta": {
    "qualityFlags": ["m18_layer_separation_candidates"],
    "layerSeparationCandidateCount": 12,
    "layerSeparationFillCandidateCount": 7,
    "layerSeparationRepairRequiredCount": 2,
    "layerSeparationEmbeddedTextCount": 1,
    "layerSeparationBlockedCount": 3
  }
}
```

M18 不新增可见 DSL 节点，不修改任何已有 element 的 `name`、`meta`、`layout`、`style`、`content`、`source`、`imageFill`、`visible` 或 `children`。M18 不切图、不删除 fallback、不做 AI inpainting、不引入 Pillow/OpenCV、不创建真实 Figma group、Component/Instance 或 Auto Layout，也不做图标、圆形、三角形、五角星或复杂图形重建。

M19 新增 local asset slice candidate harness。它生成独立 `/asset-slice-candidates` 报告，并为 M18 低风险 `image_slice_with_simple_fill_candidate` 生成本地 original slice PNG 和可选 filled slice PNG。M19 只把实验资产写入 storage 和 `assets` 表，供调试和 M20+ 使用。

M19 只允许修改 DSL 顶层 `meta`：

```json
{
  "meta": {
    "qualityFlags": ["m19_local_asset_slice_candidates"],
    "assetSliceCandidateCount": 8,
    "assetSliceFilledCandidateCount": 5,
    "assetSliceBlockedCount": 2,
    "assetSliceFailedCount": 0
  }
}
```

M19 不新增可见 DSL 节点，不修改任何已有 element 的 `name`、`meta`、`layout`、`style`、`content`、`source`、`imageFill`、`visible` 或 `children`，也不修改 DSL `assets` 数组。M19 不做正式局部 fallback 替换，不删除 fallback，不做 AI inpainting，不引入 Pillow/OpenCV，不创建真实 Figma group、Component/Instance 或 Auto Layout，也不做图标、圆形、三角形、五角星或复杂图形重建。

M20 新增 icon candidate extraction/crop harness。它生成独立 `/icon-candidates` 报告，在 M15-M17 已有结构索引限定的 component 内部寻找高置信小型 icon bbox，并用标准库 PNG 工具生成本地 icon PNG 候选资产。M20 只把 icon PNG 写入 storage 和 `assets` 表，供调试和 M21+ 使用。

M20 只允许修改 DSL 顶层 `meta`：

```json
{
  "meta": {
    "qualityFlags": ["m20_icon_candidate_extraction"],
    "iconCandidateCount": 12,
    "iconCroppedAssetCount": 12,
    "iconBlockedCount": 0,
    "iconFailedCropCount": 0
  }
}
```

M20 不新增可见 DSL 节点，不修改任何已有 element 的 `name`、`meta`、`layout`、`style`、`content`、`source`、`imageFill`、`visible` 或 `children`，也不修改 DSL `assets` 数组。M20 不做 SVG/icon 语义识别，不做图标库匹配，不做可见 icon replacement，不删除 fallback，不做 AI inpainting，不引入 Pillow/OpenCV，不创建真实 Figma group、Component/Instance 或 Auto Layout，也不做圆形、三角形、五角星或复杂图形重建。

M21 新增 icon coverage audit/placement readiness harness。它生成独立 `/icon-coverage-audit` 报告，审计 M20 已裁 icon 在原图上的覆盖情况、未来放回 DSL/Figma 前的 collision/readiness，以及局部高价值区域的 missedIconHints。M21 生成 debug overlay PNG，但 overlay 只作为调试资产，不进入 Renderer 输入。

M21 只允许修改 DSL 顶层 `meta`：

```json
{
  "meta": {
    "qualityFlags": ["m21_icon_coverage_audit"],
    "iconCoverageCandidateCount": 34,
    "iconCoveragePlacementCount": 34,
    "iconCoverageMissedHintCount": 8,
    "iconPlacementReadyCount": 0,
    "iconPlacementNeedsFallbackCoordinationCount": 30,
    "iconPlacementNeedsSliceCoordinationCount": 2,
    "iconPlacementBlockedCount": 2
  }
}
```

M21 不新增可见 DSL 节点，不修改任何已有 element 的 `name`、`meta`、`layout`、`style`、`content`、`source`、`imageFill`、`visible` 或 `children`，也不修改 DSL `assets` 数组。M21 不把 M20 icon 放进画布，不删除 fallback，不做 SVG/icon 语义识别，不做图标库匹配，不按中文文案特化，不做 AI inpainting，不引入 Pillow/OpenCV，不创建真实 Figma group、Component/Instance 或 Auto Layout。M21 overlay 只画彩色 bbox，不画文字标签。

M22 新增 region-guided icon gap candidate harness。它生成独立 `/icon-gap-candidates` 报告，消费 M21 `missedIconHints` 和少量 header、bottom nav、shortcut、trailing 局部 probe，把可靠漏裁区域补裁成本地 gap icon PNG。M22 生成 debug overlay PNG，但 gap icon 和 overlay 都只是候选/调试资产，不进入 Renderer 输入。

M22 只允许修改 DSL 顶层 `meta`：

```json
{
  "meta": {
    "qualityFlags": ["m22_icon_gap_candidates"],
    "iconGapCandidateCount": 6,
    "iconGapCroppedAssetCount": 5,
    "iconGapBlockedCount": 1,
    "iconGapFailedCropCount": 0
  }
}
```

M22 不新增可见 DSL 节点，不修改任何已有 element 的 `name`、`meta`、`layout`、`style`、`content`、`source`、`imageFill`、`visible` 或 `children`，也不修改 DSL `assets` 数组。M22 不做全局 icon detection，不做 Codia 式全量可拖动图层，不把 gap icon 放进画布，不删除 fallback，不做 SVG/icon 语义识别，不做图标库匹配，不按中文文案特化，不做 AI inpainting，不引入 Pillow/OpenCV，不创建真实 Figma group、Component/Instance 或 Auto Layout。M22 overlay 只画彩色 bbox，不画文字标签。

M23 新增 icon placement plan/layering readiness harness。它生成独立 `/icon-placement-plan` 报告，消费 M20 icon candidates、M22 gap icon candidates、M19 slice candidates 和当前 DSL collision facts，输出 placements、dedupedIcons、blockedIcons、placementOverlay 和 futureDslNodeHint。M23 不裁新 icon，不把 icon 放进画布；它只判断未来可见 icon fallback 前需要 fallback mask、slice coordination、review 还是 blocked。

M23 只允许修改 DSL 顶层 `meta`：

```json
{
  "meta": {
    "qualityFlags": ["m23_icon_placement_plan"],
    "iconPlacementPlanCount": 34,
    "iconPlacementReadyCount": 0,
    "iconPlacementNeedsFallbackMaskCount": 28,
    "iconPlacementNeedsSliceCoordinationCount": 4,
    "iconPlacementNeedsFallbackCoordinationCount": 0,
    "iconPlacementReviewRequiredCount": 0,
    "iconPlacementBlockedCount": 2,
    "iconPlacementDedupedCount": 6
  }
}
```

M23 不新增可见 DSL 节点，不修改任何已有 element 的 `name`、`meta`、`layout`、`style`、`content`、`source`、`imageFill`、`visible` 或 `children`，也不修改 DSL `assets` 数组。M23 的 `futureDslNodeHint` 只存在于 report，不是 Renderer 输入。M23 不做新的 icon crop、不做全局 icon detection、不做 Codia 式全量可拖动图层、不删除 fallback、不做 SVG/icon 语义识别、不做图标库匹配、不做 AI inpainting、不引入 Pillow/OpenCV，不创建真实 Figma group、Component/Instance 或 Auto Layout。M23 overlay 只画彩色 bbox，不画文字标签。

M24 新增 visible icon fallback replay experiment harness。它默认关闭，因为它会改变可见 DSL/Figma 输出。开启 `ICON_VISIBLE_FALLBACK_ENABLED=true` 后，M24 只消费 M23 已规划的 `needs_fallback_mask` placement，把 M20/M22 已裁出且低风险的 nav/header/leading icon 小范围回放到画布。

M24 只允许四类 DSL 改动：

```json
{
  "assets": [
    {
      "assetId": "asset_icon_candidate_005",
      "type": "image",
      "role": "asset_icon_visible_fallback",
      "url": "http://localhost:8000/files/assets/task_xxx/icons/icon_candidate_005.png",
      "format": "png",
      "width": 52,
      "height": 43,
      "storage": "local",
      "meta": {
        "stage": "m24_visible_icon_fallback",
        "sourceStage": "m20",
        "sourceIconId": "icon_candidate_005"
      }
    }
  ],
  "root": {
    "children": [
      {
        "id": "icon_fallback_cover_001",
        "type": "shape",
        "role": "icon_fallback_cover",
        "layout": { "x": 131, "y": 1532, "width": 56, "height": 47 },
        "style": { "visible": true, "opacity": 1, "fill": "#FFFFFF", "radius": 0 }
      },
      {
        "id": "visible_icon_fallback_001",
        "type": "image",
        "role": "visible_icon_fallback",
        "layout": { "x": 133, "y": 1534, "width": 52, "height": 43 },
        "source": { "assetId": "asset_icon_candidate_005" },
        "imageFill": { "mode": "fit" },
        "style": { "visible": true, "opacity": 1 }
      }
    ]
  },
  "meta": {
    "qualityFlags": ["m24_visible_icon_fallback_replay"],
    "visibleIconFallbackSelectedCount": 8,
    "visibleIconFallbackAppliedCount": 6,
    "visibleIconFallbackBlockedCount": 2,
    "visibleIconFallbackSkippedCount": 0
  }
}
```

M24 不允许修改任何已有 element 或已有 asset，不删除 fallback、original_ref、candidate_text、visible_text_replacement 或 text_replacement_cover。cover 必须是 `type: "shape"`，不是 `rect`；可见性在 `style.visible`，不是顶层 `visible`。M24 不处理没拆出来的 icon，不补 M21 missed hints，不处理 M22 blocked hints，不做新的 icon crop、不做全局 icon detection、不做 Codia 式全量可拖动图层、不做透明 PNG/SVG/icon 语义识别、不做图标库替换、不引入 Pillow/OpenCV。

M25 新增 region-guided business icon candidate harness。它生成独立 `/icon-business-candidates` 报告，在 bottom nav、primary button trailing arrow、shortcut tile、metric card、room card、trailing、tip/info 等稳定业务区域裁业务 icon 候选 PNG。M25 只把 business icon PNG 和 overlay 写入 storage 与 `assets` 表，供 M26/M27 使用。

M25 只允许修改 DSL 顶层 `meta`：

```json
{
  "meta": {
    "qualityFlags": ["m25_icon_business_candidates"],
    "iconBusinessCandidateCount": 18,
    "iconBusinessCroppedAssetCount": 16,
    "iconBusinessBlockedCount": 2,
    "iconBusinessFailedCropCount": 0
  }
}
```

M25 不新增可见 DSL 节点，不修改任何已有 element 的 `name`、`meta`、`layout`、`style`、`content`、`source`、`imageFill`、`visible` 或 `children`，也不修改 DSL `assets` 数组。M25 不把 business icon 放进画布，不做 visible replay，不处理插画、头像、建筑或床位平面图复杂资产，不做全图无边界 detection，不做 Codia 式全量拆层，不做 SVG/icon 语义识别，不做图标库匹配，不引入 Pillow/OpenCV。

M26 新增 visual perception provider benchmark harness。它生成独立 `/perception-benchmark` 报告，对比 `current_rules`、可选 OpenCV、可选 SAM2 automatic masks 和可选 UIED command adapter。

M26 不允许修改 DSL：

```json
{
  "meta": {
    "qualityFlags": []
  }
}
```

M26 即使显式启用 `PERCEPTION_BENCHMARK_ENABLED=true`，也不追加 DSL meta，不新增可见 DSL 节点，不修改任何已有 element，不修改 DSL `assets` 数组，不裁新 icon asset，不把 provider candidate/blocked/overlay 写入 Renderer 输入。M26 是评估层，不是 production replacement；OpenCV/SAM2/UIED 输出不能直接成为 DSL 权威。

M27 新增 SAM2-guided visual candidate filtering harness。它生成独立 `/sam-visual-candidates` 报告，把本地 SAM2 automatic masks 过滤成 accepted/blocked visual candidates，并写入 `backend/storage/sam_visual_candidates/{taskId}.json` 与 `asset_sam_visual_candidate_overlay` debug overlay。

M27 不允许修改 DSL：

```json
{
  "meta": {
    "qualityFlags": []
  }
}
```

M27 即使显式启用 `SAM_VISUAL_CANDIDATE_ENABLED=true`，也不追加 DSL meta，不新增可见 DSL 节点，不修改任何已有 element，不修改 DSL `assets` 数组，不裁新 icon asset，不生成透明 PNG，不把 SAM2 candidate/blocked/overlay 写入 Renderer 输入。M27 是 M28 候选池合并前的过滤证据层，不是 visible replay，也不是 Codia 式全量拆层；SAM2 mask 不能直接成为 DSL 权威。

OCR boxes 和 visual primitives 只能转成 DSL patch。这个 patch 必须经过后端结构断言，不能让模型输出直接成为 DSL 权威。

## Validation And Repair

最小校验：

- `version` 存在且为 `"0.1"`。
- `taskId` 存在。
- `page.width` 和 `page.height` 合法。
- `assets` 是数组。
- `root` 存在。
- element id 唯一。
- element type 合法。
- layout 数值合法。
- image assetId 能在 assets 中找到。
- text 元素有 content。

基础修复允许：

- 缺 `name` 自动补。
- 缺 `role` 设为 `unknown`。
- 缺 `style` 设为 `{}`。
- 缺 `children` 设为空数组。
- 缺 `opacity` 设为 `1`。
- 缺 `visible` 设为 `true`。
- 坐标小数归一。
- 非法尺寸元素剔除或修正。

修复不允许重新理解页面或多轮 AI 重排。
