# 架构总览

Image-to-Figma Design v0.1 是一个多端协作系统。当前架构重点已经收口到 M29 source truth 与 legacy M30 `/dsl` bridge，不再把 M31-M39 downstream experiments 当作 active runtime。

## System Summary

核心链路：

```text
Figma Plugin UI
-> Figma Plugin Main
-> Backend API
-> OCR
-> raw M29 / M29.2 / M29.3 / M29.4 / M29.5
-> M29 Direct compare variant
-> legacy M29.0.x bridge
-> M30 DSL materialization
-> DSL v0.1
-> Image-to-Figma Renderer
-> Figma Canvas
```

项目分类为 `multi-end-frontend`，因为它包含：

- Figma Plugin UI。
- Figma Plugin Main。
- 共享 DSL Schema。
- Image-to-Figma Renderer。
- FastAPI 后端。
- PNG evidence pipeline 和本地资产发布。

## Current Shape

当前仓库结构：

```text
figma-plugin/
backend/
packages/dsl-schema/
packages/image-to-figma-renderer/
docs/
```

当前技术栈：

- Figma 插件：TypeScript、静态 `ui.html`、Figma Plugin API、`tsup`。
- 共享包：TypeScript。
- 后端：Python、FastAPI。
- 数据：SQLite。
- 存储：本地文件存储。
- OCR：fake provider 或百度 PP-OCRv5 异步 provider。
- Evidence pipeline：M29/M29.0.x/M30 Python modules。

## Major Modules

- Plugin UI：上传、进度、完成、失败。
- Plugin Main：调用 API、轮询任务、获取 DSL、调用 Renderer、操作 Figma API。
- DSL Schema：定义后端和 Renderer 的稳定合同。
- Renderer：把 DSL 转成 Figma 节点。
- Backend API：上传、任务状态、DSL、M29 Direct report、M30 report、资产、健康检查。
- Processing Pipeline：OCR、M29 source truth chain、legacy M29.0.x bridge、M30 DSL materialization。
- Storage：原图、M29/M29.0.x/M30 evidence JSON、M29 Direct DSL/report、M30 DSL/report、发布给 renderer 的 image assets、错误日志。

## Module Boundaries

Renderer 只消费 DSL，不做 OCR、M29、图片裁切、质量评分、Auto Layout 或组件化。

后端只生成 DSL 和资产，不操作 Figma 画布。

插件 UI 不理解 OCR、M29、M30 内部细节，只展示上传、进度、完成和失败。

DSL 是 Renderer 的唯一输入合同。M29 evidence 和 OCR 是后端内部证据，不是未经 materialization 的 Renderer 输入。

M29 是 source truth 层，负责 bbox、pixel ownership、region relation、weak cluster evidence 和 replay plan。M29.4 的 cluster 只是 weak structural evidence，不提供组件化、Auto Layout、Figma Component/Instance 或 visible materialization 权限。

M29 Direct 是 compare variant，通过 `GET /api/tasks/{taskId}/m29-direct-dsl` 暴露。它不替换当前 `/api/tasks/{taskId}/dsl`。

M29.0.x + M30 是当前 `/dsl` 的 legacy bridge。M30 materialization 通过 text editability decision 决定：

```text
editable_text -> 生成 m30_text_member
graphic_text_preserve_in_fallback -> 保留在 fallback，不生成 text layer
review_text -> 保留在 report，不生成 text layer
```

这个决策不改变 DSL schema，也不让 Renderer 读取 OCR/M29 内部证据。

## Removed Legacy Path

M30.2.2 removed the frozen pre-M29 backend upload chain from active source. M29 backend downstream pruning removed M31-M39/M39.1 runtime, routes, env, tests, and ONNX proposer. Their ADRs, completed plans, old storage artifacts, and git history remain for traceability only.

Do not treat the following as current architecture:

```text
POST /api/upload
old M8-M28 debug endpoints
M31 reconstruction diagnostics
M37 hierarchy readiness
M38 hierarchy materialization
M39 content/chrome classification
M39.1 unit structure readiness
ONNX proposer
```
