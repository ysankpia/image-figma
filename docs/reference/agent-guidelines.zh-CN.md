# Agent Guidelines 中文参考快照

本文件只是根目录 `AGENTS.md` 的中文参考快照。根目录 `AGENTS.md` 是 agent 执行时的权威版本；如果两者冲突，以根目录 `AGENTS.md` 为准。

## 仓库事实源

本仓库采用 agent-first 工作流。仓库文件是事实来源，不依赖聊天记录。旧计划、ADR、legacy 草稿和旧 Codia Beta 产物只能作为背景，不能覆盖当前代码和当前 docs。

当前文档入口是 [../index.md](../index.md)。先读根目录 `AGENTS.md`，再读 `docs/index.md`，然后只读任务相关文档。

## 当前产品主线

当前分支的产品主线是 Editable Draft Layer Pipeline：

```text
Figma Plugin
-> POST /api/draft-preview
-> Go backend services/backend-go
-> OCR
-> M29 physical evidence
-> optional OpenAI-compatible vision detector
-> optional vision review/reconciliation
-> Editable Layer Graph
-> Draft Runtime DSL
-> Renderer
-> Figma editable draft
```

核心目标：

```text
PNG -> editable Figma draft
```

非目标：

```text
PNG -> Codia-like tree
PNG -> official Codia JSON byte-for-byte clone
PNG -> semantic UI control tree
PNG -> Auto Layout/component reconstruction
```

## 目录职责

- `services/backend-go/`：当前 Go Draft backend。负责 M29 physical evidence、vision detector/review、Editable Layer Graph、assets、Draft Runtime DSL、task storage 和 Go tests。
- `figma-plugin/`：插件 UI、main thread、manifest 和 bundle 检查。
- `packages/image-to-figma-renderer/`：把 validated Draft Runtime DSL 写入 Figma。
- `packages/dsl-schema/`：共享 DSL 合同。
- `backend/`：保留 Python/FastAPI historical preview/reference code。除非任务明确针对 Python `/api/upload-preview`，否则不要从这里修 Draft runtime。

## 当前运行面

Draft runtime API：

```text
POST /api/draft-preview
GET /api/draft-preview/{taskId}
GET /api/draft-preview/{taskId}/dsl
GET /api/draft-preview/{taskId}/assets/{assetId}.png
GET /api/draft-preview/{taskId}/artifacts
```

本地启动：

```bash
cd services/backend-go
DRAFT_SERVER_ADDR=127.0.0.1:8000 go run ./cmd/draftserver
```

真实 OCR / vision 配置示例：

```bash
OCR_PROVIDER=baidu_ppocrv5
BAIDU_PADDLE_OCR_TOKEN=...
DRAFT_SERVER_VISION_ENABLED=true
VISION_BASE_URL=...
VISION_MODEL=...
VISION_API_KEY=...
VISION_WIRE_API=responses
VISION_DETECTOR_CONCURRENCY=3
```

## 旧路径状态

下列名字是历史/评测材料，不是当前产品生成路径：

```text
/api/codia-preview
Generate Beta
codia_runtime.dsl.v0_2.json
codia assembly/control/tree/emitter
Python /api/upload-preview as Draft runtime
M29 Direct compare
legacy M30
M31-M39/M39.1
ONNX proposer
```

不要恢复 Codia HTTP route，也不要给 Codia packages 增加新的 generation 行为。如果 Codia 里的概念有用，必须翻译成 Draft 术语：layer ownership、asset crop、z-order、grouping 或 eval metric。

Official Codia JSON 只能用于：

```text
docs/reference/codia-samples/
services/backend-go/internal/eval/codia
cmd/drafteval
```

Generation code 不能读取 golden JSON，不能 import `internal/eval/codia`。

## 核心合同

Draft pipeline 的主合同是：

```text
editable_layer_graph.v1.json
```

第一版 visible layer kinds：

```text
Page
ReferenceImage
TextLayer
RasterLayer
ShapeLayer
GroupLayer
```

硬不变量：

- 一个 visible foreground pixel 应该只有一个 visible owner。
- 原图不能作为 visible full-page backing。
- `ReferenceImage` 只能是 hidden/locked diagnostic context。
- TextLayer 必须在同区域 RasterLayer/ShapeLayer 上方。
- RasterLayer 必须有可解析 asset。
- ShapeLayer 不应携带前景文字像素。
- 每个 emit/consume/suppress/refine 决策必须有 source refs 和 reason。

语义概念如 Button、ListView、BottomNavigation、ActionBar、EditText、Component、Instance、Auto Layout，第一版只能作为 `semanticTags` 或 eval labels，不能直接成为结构 authority。

## 代码边界

- Renderer 不导入 backend。
- Go/Python backend 不导入 plugin。
- Plugin UI 不直接调用 Figma API。
- Draft generation packages 不 import Codia eval packages。
- Shared contracts 通过明确 package contract 或 `packages/dsl-schema/` 流动，不做 ad hoc JSON mutation。

优先简单、当前可验证的实现。不要创建 `utils`、`common`、`misc` 垃圾桶模块。大型中心文件是设计压力；新行为应进入职责清楚的小包。

## 验证命令

Go backend：

```bash
cd services/backend-go
go test ./...
```

Renderer：

```bash
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
```

Plugin：

```bash
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm --filter @image-figma/figma-plugin run build
```

交付前至少检查：

```bash
git diff --check
git status --short --branch
```

真实样图或插件可见行为改动时，还要检查：

```text
editable_layer_graph.v1.json
draft_runtime.dsl.v1.json
draft_validation_report.md
asset_manifest.json
renderer/plugin warnings
```

## 修复归属层

先判断失败归属层，再改代码：

```text
source image/OCR
M29 physical evidence
vision candidate/review
Draft assembly ownership
Draft asset/export
Renderer
Plugin route/render wiring
```

不要在 Renderer 或 Plugin 里掩盖 backend ownership bug。不要按文件名、品牌、文案、固定 bbox、固定坐标、固定屏幕尺寸、主题色或业务类别写特化。
