# 一期需求

本文档定义当前 Draft MVP 必须实现的产品能力。任何不在这里的能力，默认不进入当前阶段。

## Scope

一期只支持单张 PNG 转 Figma 可编辑稿：

```text
单张 PNG
-> Go Draft backend task
-> Editable Layer Graph
-> Draft Runtime DSL
-> Figma Renderer
-> 当前 Figma 画布生成结果
```

输入限制：

- 只支持 PNG。
- 单次只处理一张图。
- 优先支持 App、小程序、移动端高保真设计稿。
- 基础兼容简单后台和简单 Web 截图。
- 不重点优化长 Landing Page、复杂报表、复杂图表、低清图片。

## Core Capabilities

P0 能力：

- 插件内选择 PNG。
- 插件内预览上传图片。
- 用户确认后开始生成。
- 后端创建任务并返回 `taskId`。
- 后端保存原图并生成 Editable Layer Graph、Draft Runtime DSL 和 raster assets。
- 后端提供任务状态、DSL 和资产访问接口。
- Renderer 消费 DSL 并在 Figma 当前画布生成 root Frame。
- Renderer 支持 `text`、`shape`、`image`、`frame`、`group` 的基础渲染。
- Renderer 返回渲染数量和 warnings。
- 生成完成或失败时插件给出明确状态。

P1 能力：

- 基础 `icon` 和 `line` 渲染。
- 原图隐藏参考层。
- fallback 图片区域。
- 基础圆角、描边、阴影。
- 字体加载失败时降级但不中断整页。

P2 能力：

- 复杂渐变。
- 更精细图标矢量化。
- 更完整 OCR 纠错。
- 更好的视觉质量评估。

## Output Requirements

Figma 输出必须包含：

- 一个 root Frame。
- 可编辑主文字。
- 基础 shape/card/background。
- 图片资产节点。
- 必要分组或 frame 层级。
- 可隐藏的原图参考层。
- 对复杂区域的 fallback 图片。

输出不要求：

- 100% 像素级一致。
- 100% 可编辑。
- 自动生成 Auto Layout。
- 生成 Figma Component。
- 生成前端代码。

## Error Requirements

所有失败必须能归到明确阶段：

- `upload`
- `preprocess`
- `ocr`
- `m29`
- `vision`
- `draft_assemble`
- `asset_crop`
- `draft_export`
- `draft_validate`
- `render`

用户看到友好错误文案。开发者能看到 `errorCode`、`stage`、`taskId` 和调试 detail。
