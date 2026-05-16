# Figma 插件架构

Figma 插件分为 UI 和 Main 两层。

## Plugin UI

M5 当前 Plugin UI 使用静态 `ui.html`、内联 CSS/JS 和 TypeScript Main。这个选择来自现有已审核 Figma 插件的壳子经验，目的是先用最少移动部件打通 UI -> Main -> Backend -> Renderer -> Figma Canvas。

React + TypeScript + Vite 不是当前实现前提。后续如果上传、预览、进度、错误恢复和设置页变复杂，再单独评估是否引入 React/Vite。

职责：

- 上传 PNG。
- 显示文件信息。
- 触发开始生成。
- 显示进度。
- 显示完成或失败。
- 保留 sample DSL 生成作为开发备用入口。

不负责：

- 创建 Figma 图层。
- 渲染 DSL。
- OCR。
- AI 分析。
- 图片裁切。
- DSL 生成。

## Plugin Main

Plugin Main 运行在 Figma 插件主线程。

职责：

- 接收 UI 消息。
- 调用后端 API。
- 轮询任务状态。
- 获取 DSL。
- 调用 Renderer。
- 使用 Figma Plugin API 创建图层。
- 返回结果给 UI。

## Views

M5 当前静态工具面板：

- `Choose PNG`。
- `Generate from PNG`。
- `Sample` 开发备用入口。
- 当前状态。
- warning 列表。
- 关闭按钮。

后续 v0.1 完整产品流程再补：

- `PreviewView`
- `ProgressView`
- `DoneView`
- `ErrorView`

不做设置页、账号页、历史页、质量报告页、批量上传页。

## Message Flow

M3 当前流：

```text
UI clicks Generate sample design
-> Main receives render-sample
-> Main loads bundled mobile-home DSL
-> Main calls Renderer
-> Main reports success, warnings, or failure
```

后续接入后端后的完整流：

```text
UI selects PNG
-> Main uploads PNG
-> Main polls task
-> Main fetches DSL
-> Main calls Renderer
-> Main reports done or error
```

M5 保留开发备用流：

```text
UI clicks Sample
-> Main loads bundled mobile-home DSL
-> Main calls Renderer
```

M9 没有改插件协议。插件不调用 `/api/tasks/{taskId}/primitives`、`/ocr` 或 `/dsl-patch`，也不展示 AI/OCR/primitive/patch 内部结果。默认 enhanced DSL 里的 OCR text candidates 是 hidden，不改变用户可见生成结果。

## User Language

插件 UI 不暴露内部术语：

- 不显示 OCR。
- 不显示 AI 分析。
- 不显示 DSL。
- 不显示模型调用。
- 不显示质量评分。

用户只需要看到：

- 上传中。
- 处理中。
- 生成中。
- 正在写入 Figma。
- 生成完成。
- 生成失败。
