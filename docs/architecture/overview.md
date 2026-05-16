# 架构总览

Image-to-Figma Design v0.1 是一个多端协作系统，不是单纯后端服务。

## System Summary

核心链路：

```text
Figma Plugin UI
-> Figma Plugin Main
-> Backend API
-> Processing Pipeline
-> DSL v0.1
-> Image-to-Figma Renderer
-> Figma Canvas
```

项目分类为 `multi-end-frontend`，因为它包含：

- Figma Plugin UI。
- Figma Plugin Main。
- 共享 DSL Schema。
- Image-to-Figma Renderer。
- 后端 API。
- 图片识别和资产裁切管线。

## Current Shape

当前仓库已经进入 MVP 工程阶段，核心结构：

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
- 后端：Python、FastAPI、Pydantic。
- 数据：SQLite。
- 存储：本地文件存储。
- PNG region slicer：Python 标准库。
- Visual primitives：M8 已建立合同和 fake/OpenAI provider 边界，结果不进入 DSL。
- OCR/DSL patch：M9 已建立 fake OCR 和 hidden candidate patch harness，不做可见替换。

## Major Modules

- Plugin UI：上传、预览、进度、完成、失败。
- Plugin Main：调用 API、轮询任务、获取 DSL、调用 Renderer、操作 Figma API。
- DSL Schema：定义后端和 Renderer 的稳定合同。
- Renderer：把 DSL 转成 Figma 节点。
- Backend API：上传、任务状态、DSL、资产、健康检查。
- Processing Pipeline：预处理、裁切、visual primitive candidates、OCR candidates、DSL patch、DSL Builder、校验和基础修复。
- Storage：原图、资产、DSL 结果、primitive 结果、OCR 结果、patch 结果、日志。

## Module Boundaries

Renderer 只消费 DSL，不做 OCR、AI、图片裁切、DSL 生成、质量评分、Auto Layout、组件化。

后端只生成 DSL 和资产，不操作 Figma 画布。

插件 UI 不理解 OCR、AI、DSL 内部细节，只展示上传、预览、进度、完成、失败。

DSL 是 Renderer 的唯一输入合同。Visual primitives、OCR 和 DSL patch 是候选调试合同，不是未经校验的 DSL 权威。后端和 Renderer 的任何协议变化必须先更新 [dsl.md](dsl.md) 和 [api-contracts.md](api-contracts.md)。
