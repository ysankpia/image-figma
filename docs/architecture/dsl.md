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

M6 deterministic fallback DSL 固定使用整图 fallback：

- `original_ref`：隐藏原图参考层。
- `fallback_full_image`：可见整图 fallback。
- `meta.notes`：`deterministic_fallback_dsl`。

M6 不识别文字、图标或真实布局。后续 OCR/AI 管线必须在不破坏该 fallback 保障的前提下逐步增加可编辑元素。

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
