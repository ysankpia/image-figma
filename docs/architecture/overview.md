# 架构总览

Image-to-Figma Design 是一个多端协作系统。当前 Codia Beta 架构重点已经切到 Go Codia compiler：Go M29 physical evidence、可选 VLM detector、assembly/control/tree/emitter、DSL v0.2 Codia Runtime 和插件 `Generate Beta`。Python/FastAPI `/api/upload-preview` 仍保留为 DSL v0.1 M29 preview 路径，但不是 Codia Beta 输出质量调试的主线。

## System Summary

当前 Codia Beta 核心链路：

```text
Figma Plugin UI
-> Figma Plugin Main
-> Go codiaserver /api/codia-preview
-> OCR
-> Go M29 physical evidence
-> optional OpenAI-compatible UI detector
-> Codia assembly/control/tree/emitter
-> DSL v0.2 Codia Runtime
-> renderCodiaRuntimeDesign
-> Figma Canvas
```

项目分类为 `multi-end-frontend`，因为它包含：

- Figma Plugin UI。
- Figma Plugin Main。
- 共享 DSL Schema。
- Image-to-Figma Renderer。
- Go Codia Beta 后端。
- 保留的 Python/FastAPI preview 后端。
- PNG evidence pipeline 和本地资产发布。

## Current Shape

当前仓库结构：

```text
figma-plugin/
services/backend-go/
backend/
packages/dsl-schema/
packages/image-to-figma-renderer/
docs/
```

当前技术栈：

- Figma 插件：TypeScript、静态 `ui.html`、Figma Plugin API、`tsup`。
- 共享包：TypeScript。
- Codia Beta 后端：Go、标准库 HTTP、标准库 PNG/image 处理。
- 保留 preview 后端：Python、FastAPI。
- 数据：本地 task JSON / SQLite 视具体运行面而定。
- 存储：本地文件存储。
- OCR：fake provider 或百度 PP-OCRv5 异步 provider。
- Codia Beta evidence pipeline：Go M29 physical evidence + Codia assembly。
- 保留 preview evidence pipeline：Python M29 modules。

## Major Modules

- Plugin UI：上传、进度、完成、失败。
- Plugin Main：调用 API、轮询任务、获取 DSL、调用 Renderer、操作 Figma API。
- DSL Schema：定义后端和 Renderer 的稳定合同。
- Renderer：把 DSL 转成 Figma 节点。
- Go Codia Beta Backend：`/api/codia-preview` 上传、任务状态、DSL v0.2、Codia artifacts、crop assets、健康检查。
- Python Preview Backend：`/api/upload-preview` 上传、任务状态、DSL v0.1、M29 materialization report、资产、健康检查。
- Processing Pipeline：Go Codia Beta 路径使用 OCR、Go M29 physical evidence、detector candidates、assembly/control/tree/emitter；Python preview 路径使用 M29 source truth chain 和 M29.5 replay plan。
- Storage：原图、M29/Codia evidence JSON、DSL/report、发布给 renderer 的 image assets、错误日志。

## Module Boundaries

Renderer 只消费 DSL，不做 OCR、M29、图片裁切、质量评分、Auto Layout 或组件化。

后端只生成 DSL 和资产，不操作 Figma 画布。Codia Beta 后端在 `services/backend-go`；Python `backend/app` 不承载 Codia Beta assembly/tree/DSL v0.2 修复。

插件 UI 不理解 OCR、M29 内部细节，只展示上传、进度、完成和失败。

DSL 是 Renderer 的唯一输入合同。Codia Beta Renderer 消费 DSL v0.2 Codia Runtime；默认 preview Renderer 消费 DSL v0.1。M29/Codia evidence 和 OCR 是后端内部证据，不是未经 materialization 的 Renderer 输入。

M29 是 source truth 层，负责 bbox、pixel ownership、region relation、weak cluster evidence 和 replay plan。M29.4 的 cluster 只是 weak structural evidence，不提供组件化、Auto Layout、Figma Component/Instance 或 visible materialization 权限。

M29 plan-driven materializer 是当前正式 DSL producer。它只消费 M29.5 plan，不重新判断 owner，不按主题、颜色、截图、文案或行业特化，不把 weak cluster 转成组件。

## Removed Legacy Path

M30.2.2 removed the frozen pre-M29 backend upload chain from active source. Later pruning removed M31-M39/M39.1 runtime, routes, env, tests, and ONNX proposer. This stage also removed the M29 Direct compare product endpoint and legacy M30 materialization product path. Their ADRs, completed plans, old storage artifacts, and git history remain for traceability only.

Do not treat the following as current architecture:

```text
POST /api/upload
GET /api/tasks/{taskId}/m29-direct-dsl
GET /api/tasks/{taskId}/m30-materialization
old M8-M28 debug endpoints
M29.0.x legacy bridge as product source truth
M30 evidence-grounded materializer as product source truth
M31 reconstruction diagnostics
M37 hierarchy readiness
M38 hierarchy materialization
M39 content/chrome classification
M39.1 unit structure readiness
ONNX proposer
```
