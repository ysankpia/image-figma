# 架构总览

当前分支的可交付架构目标是 **Slice Studio**：把 1..N 张 UI 截图或设计图整理成用户确认后的切图资产和 Pencil/Figma handoff 包。

```text
1..N UI screenshots/design images
-> repository root
-> project workspace
-> saved SliceRecord boxes in SQLite
-> assets.zip
-> project.zip / design.pen
```

这不是 Codia-like tree、自动 Figma layer reconstruction、Auto Layout 还原或 Go Draft 一键生成路线。旧 Pencil Python、Go Draft、Renderer、Figma plugin、PSD-like、Codia eval 和旧 M29 研究代码保留为 reference/fallback/deferred runtime/legacy research。

## Current System

当前系统边界集中在仓库根目录：

- Next.js web app：项目首页、Review Workbench、画框、页面管理、资产总览和导出入口。
- Elysia API：项目、页面、切片、源图、AI 画框、预览图、ZIP 导出。
- SQLite storage：项目、页面、slice 元数据。
- Local file storage：原图、导出包、可预览切片。
- Exporters：`assets.zip` 和 `project.zip/design.pen`。
- OCR/M29 text handoff：OCR 提供文字内容，TypeScript M29 physical evidence 提供更紧的文字物理 bbox。
- AI slice boxes：模型只看压缩 tile/overview 并返回 bbox；前端把 bbox 转成普通 `SliceRecord`。

## Current Product Mainline

```text
GET /projects
-> POST /api/projects
-> POST /api/projects/:projectId/pages
-> Review Workbench draw or AI-generate SliceRecord boxes
-> PUT /api/projects/:projectId/slices
-> POST /api/projects/:projectId/export-assets
-> GET /api/projects/:projectId/assets.zip
-> POST /api/projects/:projectId/export-project
-> GET /api/projects/:projectId/project.zip
```

## Main Contracts

- Saved Slice Studio pages and slices：当前编辑、保存、导出的 truth source。
- `manual_ui_slices.v1`：Slice Studio export manifest schema。
- `assets.zip`：前端切图资产包。
- `project.zip/design.pen`：Pencil/Figma handoff 包。
- AI boxes：短生命周期建议，进入前端后等同普通 slice。
- OCR output：文字内容证据。
- `M29PhysicalEvidence` TypeScript document：OCR text bbox physical evidence。

Historical contracts:

- `manual_slices.v1.json`：旧 Python Pencil assisted slice truth source。
- `editable_layer_graph.v1.json`：历史 Go Draft 后端合同。
- `draft_runtime.dsl.v1.json`：历史 Renderer 输入合同。
- `draft_validation_report.md` / `asset_manifest.json`：历史 Draft artifact 合同。

## Module Boundaries

Slice Studio exporter 只读取保存后的 SliceRecord 和源图，不重新判断 UI ownership。

AI slice boxes 只能提供候选 bbox。它不写数据库、不创建 proposal 状态、不读 M29/OCR、不生成最终导出结构。

OCR 只负责文字内容和原始 OCR bbox。它不重建按钮、卡片、图标、图片、背景或 Auto Layout。

TypeScript M29 physical evidence 只服务 OCR line bbox placement。它不创建 visible layers，不覆盖用户确认的 slice，不要求 Go binary。

Go `m29extract` 是显式 fallback/reference。默认 Slice Studio 部署不依赖 Go M29 binary。

`assets.zip` 与 `project.zip` 使用同一套已确认 slice 和 cut mode 逻辑。不得再引入第二套可见资产 ownership pipeline。

## Legacy Boundaries

以下不是当前默认生成架构：

```text
archive/legacy-code/services/pencil-python-backend as default product server
archive/legacy-code/services/pencil-asset-backend as default asset server
archive/legacy-code/services/pencil-handoff-studio as default handoff server
Go Draft /api/draft-preview as default route
Python /api/upload-preview as default route
Codia assembly/control/tree/emitter
Generate Beta as product mainline
visible full-image backing as final output
M29 Direct compare
legacy M30 materialization
M31-M39/M39.1 runtime
ONNX proposer
```

旧代码可作为研究资产和恢复参考。恢复任何旧路线前，必须先写 active plan，定义新的 truth source、runtime contract、验收样例和回退策略。
