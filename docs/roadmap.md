# Image-to-Figma Roadmap

- 状态：active
- 更新日期：2026-05-31

## Purpose

本文档固定当前路线，避免后续工作继续在旧 Python preview、Codia-like tree、官方 Codia JSON、组件化、Auto Layout 和代码生成之间来回跳。

当前产品目标只有一个：

```text
PNG -> editable Figma draft
```

当前主线是 Editable Draft Layer Pipeline：

```text
PNG
-> OCR + M29 physical evidence + optional vision detector/review
-> Editable Layer Graph
-> Draft Runtime DSL
-> Renderer
-> Figma editable draft
```

第一性原理边界：

```text
PNG 像素是输入真相源。
M29/OCR 提供物理证据。
Vision provider 提供语义候选和 review，不生成最终树。
Draft assembly 是 layer ownership authority。
Renderer 只机械渲染 DSL，不修 ownership。
Codia golden 只做 eval/reference，不进入 generation。
```

硬不变量：

```text
one visible foreground pixel -> one visible owner
```

这条不变量优先级高于下游 grouping、视觉相似度和节点数量。它不禁止 Figma layer bbox 重叠；背景 shape 可以和 child text/image/icon 在空间上重叠，因为它们拥有不同 source evidence。

## Current Runtime Surfaces

当前 Go Draft 主链：

```text
Figma Plugin Generate Draft
-> POST /api/draft-preview
-> Go draftserver
-> OCR
-> Go M29 physical evidence
-> optional OpenAI-compatible vision detector/review
-> Editable Layer Graph
-> Draft Runtime DSL
-> GET /api/draft-preview/{taskId}/dsl
-> GET /api/draft-preview/{taskId}/assets/{assetId}.png
-> renderDraftRuntimeDesign
-> Figma Canvas
```

当前 Draft 输出质量、vision、M29、layer ownership、asset、DSL、renderer 和插件 wiring 问题都先归到：

```text
services/backend-go/internal/m29
services/backend-go/internal/vision
services/backend-go/internal/draft
services/backend-go/internal/app
packages/image-to-figma-renderer
figma-plugin
```

旧运行面状态：

- Python/FastAPI `/api/upload-preview`：历史 preview/reference path，不是 Draft runtime。
- Codia generation path：已从产品代码移除。
- Official Codia JSON：eval/reference material only。

## What To Improve Next

### 1. Stabilize Draft Layer Ownership

最高优先级是让真实样图稳定生成可编辑草稿，而不是继续追一个 Codia-like semantic tree。

重点：

- TextLayer 必须在同区域 Shape/Raster 上方。
- 原图不能作为 visible full-page backing。
- RasterLayer 必须有可解析 asset。
- ShapeLayer 不应携带前景文字像素。
- 普通 OCR 文本默认保留为可编辑文本。
- 只有局部媒体、图标、头像、封面、缩略图等 compact evidence 才成为 RasterLayer。
- 所有 emit/consume/suppress/refine 决策必须有 source refs 和 reason。

### 2. Vision + M29 Reconciliation

Vision 不是最终 authority。它补语义、补漏、做二次 review；M29/OCR 提供更硬的 bbox 和像素证据。

需要继续收敛：

- detector pass 并发和 deterministic merge。
- VLM review 对 M29 缺失/碎片/误报的二次校验。
- 越界、空响应、TLS/provider 失败时的 fallback artifact。
- provider/baseUrl/model/apiKey/stream/concurrency 全部保持可配置。

### 3. Real Sample Validation

每次改 Draft pipeline 都要跑真实样例，而不是只看单元测试。

当前最小样例集：

```text
Tencent 018
Tencent 022
Lizhi 011
Xianyu
```

验收信号：

- asset missing = 0。
- plugin image load failed = 0。
- visible full-page backing = 0。
- TextLayer covered by RasterLayer = 0。
- unauthorized large sibling overlap = 0。
- ordinary OCR text remains editable。
- major regions can be moved as groups。

### 4. Code Slimming

重构方向是删掉错误抽象，不是给旧 Codia-like pipeline 打补丁。

优先整理：

```text
internal/draft/assemble
internal/draft/group
internal/vision/detector
internal/m29/pipeline
internal/app/server
```

原则：

- 行为变更和命名/拆文件分开提交。
- 不创建 `utils`、`common`、`misc` 垃圾桶。
- 不恢复 `codia`、`tree`、`control`、`leaf`、`emitter`、`compiler` 作为产品生成命名。

### 5. Eval, Not Generation

Codia 仍有用，但只在 eval/reference 层有用。

允许：

```text
docs/reference/codia-samples/
services/backend-go/internal/eval/codia
cmd/drafteval
```

禁止：

```text
generation imports internal/eval/codia
generation reads Codia golden JSON
new product endpoint named codia
official Codia JSON as output target
```

## Non-Goals For The Next Phase

下一阶段不要做：

```text
Auto Layout
Figma Component/Instance
frontend code generation
official Codia JSON clone
semantic UI control tree as product contract
batch upload
quality dashboard
account/payment/quota
```

这些不是永远不做。它们被阻塞到 Draft layer ownership、asset、z-order、grouping 和真实样图验证稳定之后。
