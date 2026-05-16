# 用户流程

一期只有一条主流程：插件上传单张 PNG，生成 Figma 可编辑稿。

## 主流程

```text
打开 Figma 插件
-> 选择 PNG
-> 插件显示预览和文件信息
-> 用户点击开始生成
-> 插件上传图片并创建任务
-> 插件轮询任务状态
-> 后端返回 DSL
-> Plugin Main 调用 Renderer
-> Renderer 写入 Figma 画布
-> 插件显示完成
```

## 页面状态

插件 v0.1 只需要五个状态：

- `UploadView`：选择 PNG。
- `PreviewView`：显示图片预览、文件名、尺寸、大小和风险提示。
- `ProgressView`：显示生成中状态。
- `DoneView`：显示生成完成。
- `ErrorView`：显示失败原因和重试入口。

普通用户不看 OCR、AI、DSL、模型调用、质量评分等内部术语。

## 失败流程

上传前失败：

- 非 PNG：拒绝。
- 文件过大：拒绝。
- 图片无法读取：拒绝。

处理中失败：

- 后端返回 `failed`。
- 插件进入 `ErrorView`。
- 错误文案使用用户语言，调试信息进入日志或开发模式。

渲染中局部失败：

- 单个元素失败不影响整页。
- Renderer 收集 warning。
- 能 fallback 的区域用图片兜底。

## 生成位置

一期默认生成到当前 Figma 页面。Renderer 创建一个 root Frame，内部包含生成图层。原图参考层默认隐藏，但保留在 root Frame 内。

## 轮询策略

插件查询任务状态：

- 默认间隔：1 到 2 秒。
- 超过合理时间后提示超时。
- 不做 WebSocket、队列面板、历史任务列表。
