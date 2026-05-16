# Figma 插件架构

Figma 插件分为 UI 和 Main 两层。

## Plugin UI

Plugin UI 使用 React + TypeScript + Vite。

职责：

- 上传 PNG。
- 显示预览。
- 显示文件信息。
- 显示质量风险提示。
- 触发开始生成。
- 显示进度。
- 显示完成或失败。

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

v0.1 只需要：

- `UploadView`
- `PreviewView`
- `ProgressView`
- `DoneView`
- `ErrorView`

不做设置页、账号页、历史页、质量报告页、批量上传页。

## Message Flow

```text
UI selects PNG
-> Main uploads PNG
-> UI shows preview
-> UI starts generation
-> Main polls task
-> Main fetches DSL
-> Main calls Renderer
-> Main reports done or error
```

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
