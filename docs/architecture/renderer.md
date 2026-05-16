# Image-to-Figma Renderer

Renderer 的职责只有一个：把 DSL v0.1 渲染成 Figma 节点。

## Responsibilities

Renderer 必须做：

- 校验 DSL version。
- 做轻量 DSL 校验。
- 建立 asset 索引。
- 创建 root Frame。
- 递归渲染 children。
- 渲染 `frame`、`group`、`text`、`shape`、`image`、`icon`、`line`。
- 应用 layout 和基础 style。
- 加载图片资产。
- 渲染原图隐藏参考层。
- 渲染 fallback 区域。
- 收集 warnings。

## Non-Responsibilities

Renderer 不做：

- OCR。
- AI 分析。
- 图片裁切。
- DSL 生成。
- 业务语义判断。
- 页面类型判断。
- Auto Layout。
- Figma Component。
- 代码生成。
- 质量评分。

## Rendering Priority

P0：

- root Frame。
- Text。
- Shape。
- Image。
- layout。
- fill。
- radius。
- opacity。
- visible。

P1：

- Icon。
- Line。
- shadow。
- stroke。
- font loading。
- original reference。
- fallback。

P2：

- gradient。
- 复杂 SVG 改色。
- 图片并发加载优化。
- 高级 effects。

## Failure Policy

单个元素失败不能导致整页失败。

Renderer 返回结果应包含：

- 是否成功。
- root Frame 或失败信息。
- `renderedElementCount`。
- warnings。
- errors。

如果图片加载失败：

- 记录 warning。
- 用占位 shape 或跳过该元素。
- 不中断整页。

如果字体加载失败：

- 降级到默认字体。
- 记录 warning。
- 不中断整页。

## Layer Policy

- root Frame 使用页面尺寸。
- 图层命名优先使用 `name`，缺失时使用 `type` 和 `id`。
- 原图参考层默认隐藏。
- fallback 区域作为 image 渲染。
- children 按 DSL 顺序渲染，保持图层顺序可预测。
