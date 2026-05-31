# Figma 插件架构

Figma 插件分为 UI 和 Main 两层。当前主线是 `Generate Draft`：上传 PNG 到 Go `/api/draft-preview`，获取 Draft Runtime DSL 和 assets，并通过 Renderer 写入 Figma。

## Plugin UI

Plugin UI 使用静态 `ui.html` 和 TypeScript Main。它负责：

- 选择 PNG。
- 触发 Draft 生成。
- 显示文件信息。
- 显示任务进度。
- 显示完成、失败和 warnings。
- 保留 sample 渲染作为开发备用入口。

不负责：

- 创建 Figma 图层。
- 渲染 DSL。
- OCR。
- VLM 分析。
- 图片裁切。
- Draft layer ownership。
- 选择 Codia/Python/legacy 路线。

## Plugin Main

Plugin Main 运行在 Figma 插件主线程。

职责：

- 接收 UI 消息。
- 调用 `/api/draft-preview`。
- 轮询 Draft task。
- 获取 Draft Runtime DSL。
- 设置 asset base URL。
- 调用 Renderer。
- 使用 Figma Plugin API 创建图层。
- 返回结果、warnings 或错误给 UI。

## Views

当前静态工具面板：

- `Choose PNG`
- `Generate Draft`
- `Sample`
- 当前状态
- warning 列表
- 关闭按钮

不要在产品 UI 中暴露：

```text
OCR
M29
VLM
DSL
Codia
质量评分
内部路线选择
```

## Message Flow

Sample 开发备用流：

```text
UI clicks Sample
-> Main receives render-sample
-> Main loads bundled sample DSL
-> Main calls Renderer
-> Main reports success, warnings, or failure
```

Draft 上传流：

```text
UI selects PNG
-> UI clicks Generate Draft
-> Main uploads PNG to /api/draft-preview
-> Main polls /api/draft-preview/{taskId}
-> Main fetches /api/draft-preview/{taskId}/dsl
-> Main calls Renderer with assetBaseUrl=/api/draft-preview/{taskId}
-> Main reports done or error
```

## Boundary

The plugin must render the backend contract. It must not hide backend ownership bugs with sample-specific layer suppression, text order patches, or asset fallback hacks.
