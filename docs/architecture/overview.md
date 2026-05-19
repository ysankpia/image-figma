# 架构总览

Image-to-Figma Design v0.1 是一个多端协作系统。

## System Summary

核心链路：

```text
Figma Plugin UI
-> Figma Plugin Main
-> Backend API
-> OCR + M29 + M30 Processing Pipeline
-> DSL v0.1
-> Image-to-Figma Renderer
-> Figma Canvas
```

M31 是当前新增的诊断组织层，M31.1 会随上传链路生成诊断产物，但不改变 DSL/Renderer/Figma 可见输出：

```text
source PNG + OCR JSON + M29 nodes.json
-> M31 Reconstruction UI Tree
-> reconstruction units with fallback crops
```

它的作用是把 M29 的碎 primitive evidence 组织成可回退的 reconstruction units，为后续 M32/M33/M34 服务。

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
- Evidence pipeline：M29/M30 Python modules。

## Major Modules

- Plugin UI：上传、进度、完成、失败。
- Plugin Main：调用 API、轮询任务、获取 DSL、调用 Renderer、操作 Figma API。
- DSL Schema：定义后端和 Renderer 的稳定合同。
- Renderer：把 DSL 转成 Figma 节点。
- Backend API：上传、任务状态、DSL、M30/M31 report、资产、健康检查。
- Processing Pipeline：OCR、M29 evidence、M31 diagnostics、M30 DSL materialization。
- M31 Reconstruction UI Tree：上传旁路诊断，把 M29 primitive refs 组织成 reconstruction units。
- Storage：原图、M29/M30 evidence JSON、M30 DSL/report、发布给 renderer 的 image assets、错误日志。

## Module Boundaries

Renderer 只消费 DSL，不做 OCR、M29、图片裁切、质量评分、Auto Layout 或组件化。

后端只生成 DSL 和资产，不操作 Figma 画布。

插件 UI 不理解 OCR、M29、M30 内部细节，只展示上传、进度、完成和失败。

DSL 是 Renderer 的唯一输入合同。M29 evidence 和 OCR 是后端内部证据，不是未经 M30 materialization 的 Renderer 输入。

M31 tree 也不是 Renderer 输入。它是 evidence organization 层，用来验证 primitive ownership、unit fallback coverage 和后续 layer recovery 的可行性。

## Removed Legacy Path

M30.2.2 removed the frozen pre-M29 backend upload chain from active source. `POST /api/upload`, old task debug endpoints, and the old M8-M28 runtime modules are historical only. Keep their old ADRs and archived docs for traceability, but do not treat them as current architecture.
