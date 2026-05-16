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

M13 在 M12 decision 后增加 quality gate。只有 `decision=accepted` 且 `quality.applyEligible=true` 的 replacement 会进入 DSL；被阻断的 accepted decision 只保留在 `/text-replacements` 报告里。DSL meta 可包含 `m13_text_replacement_quality_control`、`textReplacementAppliedCount` 和 `textReplacementBlockedCount`。

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
