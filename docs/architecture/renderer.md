# Image-to-Figma Renderer

Renderer 的职责是把后端已经裁决好的 DSL 渲染成 Figma 节点。当前 Codia Beta 使用 Go 后端输出的 DSL v0.2，并通过 `renderCodiaRuntimeDesign` 写入 Figma。保留的 Python preview 路径仍使用 DSL v0.1 和 `renderDesign`。

## Public Interface

当前公共入口：

```ts
renderDesign(dsl, options)
```

Go Codia Beta 入口：

```ts
renderCodiaRuntimeDesign(dsl, options)
```

`options` 必须提供 `FigmaAdapter`。Renderer 不直接依赖全局 `figma`，真实 Figma API 只在 adapter 中封装。

返回结果包含：

- `success`
- `rootNodeId`
- `renderedElementCount`
- `warnings`
- `errors`

## Responsibilities

Renderer 必须做：

- 校验 DSL version。
- 做轻量 DSL 校验。
- 建立 asset 索引。
- 创建 root Frame。
- 递归渲染 children。
- 渲染 `frame`、`group`、`text`、`shape`、`image`、`line`。
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
- Codia ownership / consume / suppress 仲裁。
- 页面类型判断。
- Auto Layout。
- Figma Component。
- 代码生成。
- 质量评分。
- 直接在业务模块里使用全局 `figma`。

## Rendering Priority

P0：

- root Frame。
- Text。
- Shape。
- Image。
- Line。
- 原图隐藏参考层。
- fallback image。
- layout。
- fill。
- radius。
- opacity。
- visible。

P1：

- Icon。
- shadow。
- stroke。
- font loading。

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

如果遇到 icon：

- v0.1 M2 记录 `UNSUPPORTED_ELEMENT_TYPE` warning。
- 继续渲染其他元素。

## Layer Policy

- root Frame 使用页面尺寸。
- 图层命名优先使用 `name`，缺失时使用 `type` 和 `id`。
- 原图参考层默认隐藏。
- fallback 区域作为 image 渲染。
- children 按 DSL 顺序渲染，保持图层顺序可预测。
- `style.fill = null` 表示显式无填充。Renderer 必须清空 Figma fills，供普通透明 group/frame 使用。历史 M38 透明 hierarchy group 已不属于当前 backend runtime。

## Boolean Subtraction for Fallback Nodes

为了防止在已 Materialize 激活的文本/图标与假底图（fallback region）之间发生双重渲染（ghosting/双层显示），Renderer 实现了 Figma 原生 Boolean Subtraction：

- **Figma API 集成**：在 `FigmaAdapter` 接口中扩展了 `createBooleanSubtract(nodes: FigmaNode[], parent?: FigmaNode): FigmaNode` 方法，该方法在真实插件运行时委托给 Figma 原生的 subtraction group API。
- **触发条件**：在渲染 `image` 元素时，如果其 `meta` 属性包含 `maskBBoxes` 数组（绝对坐标），Renderer 不会将其渲染为普通的 `RECTANGLE` 节点，而是自动进行布尔差集组合。
- **构建工作流**：
  1. 创建 base image 矩形节点（带图片填充和对应尺寸）。
  2. 根据 `maskBBoxes` 的坐标，为每个 mask region 生成一个 dummy 矩形节点。
  3. 调用 `createBooleanSubtract([baseNode, ...maskNodes], parent)` 构建一个 Boolean Subtract 分组。
  4. 最终生成的 subtraction 组合节点接收该 image 元素的 user-visible `name`，而内部的 base node 则会被命名为 `Image / <id>`，保证 Figma 图层结构的美观与可读。
  5. 差集计算时，原 base node 和 dummy 矩形节点会被自动从父级 Frame 的 flat children 列表中移除，转而归属于 subtraction 组中。

## Dev Harness

当前 `figma-plugin/` 只提供开发烟测插件：

- 入口：`figma-plugin/src/dev-main.ts`
- 构建产物：`figma-plugin/dist/dev-main.global.js`
- Manifest：`figma-plugin/manifest.json`

它加载 `mobile-home.dsl.json`，调用 Renderer，并把 root Frame 写入当前 Figma 页面。它不是正式插件 UI。
