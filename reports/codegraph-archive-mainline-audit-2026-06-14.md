# CodeGraph 代码事实梳理：archive 与当前主业务

生成时间：2026-06-14

仓库：`/Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma`

事实来源：CodeGraph 对当前代码的符号/调用关系、源码入口文件、包配置、测试代码、目录结构统计。

约束：本报告不读取、不引用现有 `docs/` 作为事实来源。旧 README、计划文档、历史说明也不作为判断依据。下面的判断只基于代码。

## 总判断

当前仓库的真实主业务已经不是 `archive/legacy-code` 里的 Figma 插件、Draft Runtime DSL、旧 Python/Go Pencil 后端，也不是旧 PSD-like 全链路。当前主业务是根目录的 Slice Studio：

```text
Next/React/Konva 前端
-> Elysia API
-> SQLite + storage/projects
-> 用户保存的 SliceRecord
-> assets.zip 或 Pencil project.zip/design.pen
```

`archive/legacy-code` 是多条历史路线的集合，其中有可复用的算法和合同，但不能当作当前产品事实。最有价值的旧资产是：

1. `pencil-python-backend/app/exporter/single_page.py` 里的三模式 Pencil 导出思想，尤其是 `clean-editable` 的文字 knockout 约束。
2. `services/backend-go/internal/m29` 的 Go M29 物理证据生成和 surface/text primitive 思路。
3. `packages/dsl-schema` + `packages/image-to-figma-renderer` 的 DSL 中间合同和 Figma 渲染器。
4. `services/psdlike-python` 与当前 `services/psdlike-text-style` 中的文本样式估计、背景采样、文字 knockout mask 思路。

但当前可交付路径已经收敛到 Pencil `.pen` 包：底图 remainder + 可编辑文本 + 已确认 slices。不要再把旧 DSL、旧 Figma 插件、旧 Python/Go server 直接混回主链路。正确用法是抽取少量代码事实和算法思想，重新用当前 TS/Elysia/Pencil 合同表达。

判断强度：强。入口文件、配置、API、测试、导出代码都指向同一个主链路。

## 代码量级与目录事实

排除 `.venv`、`.pytest_cache`、`__pycache__`、`node_modules`、`dist` 后，当前主业务代码量级：

| 区域 | 文件数 | 主要类型 |
|---|---:|---|
| `server/` | 32 | TypeScript |
| `app/` | 6 | Next App Router + CSS |
| `components/` | 4 | React/Konva UI |
| `shared/` | 7 | 共享类型、校验、zip、manifest |
| `tests/` | 9 | Vitest |
| `services/psdlike-text-style/` | 10 | FastAPI style-only 微服务 |

`archive/legacy-code` 代码量级：

| 区域 | 非生成文件数 | 事实判断 |
|---|---:|---|
| `archive/legacy-code/Figma-design` | 28 | 第一代本地 JS/Figma 插件/手动切图实验 |
| `archive/legacy-code/backend` | 765 | Python M29/视觉审计/上传预览/大量实验模块 |
| `archive/legacy-code/figma-plugin` | 11 | workspace 化的 Figma 插件 |
| `archive/legacy-code/packages` | 50 | DSL schema + Figma renderer |
| `archive/legacy-code/services` | 289 | Python/Go 后端服务集合 |
| `archive/legacy-code/tests` | 4 | 空测试占位 |

目录中还存在大量运行产物：`.venv`、`.pytest_cache`、`__pycache__`、`storage/*.db`、`storage/**/*.pen`、`storage/**/*.zip`、`dist`、`repomix-output.xml`。这些不是源代码事实，只能说明历史运行过很多实验。

## 当前主业务：运行结构

根目录 `package.json` 定义当前产品名为 `slice-studio`，运行面是：

```json
{
  "dev": "concurrently \"bun run dev:text-style\" \"bun run dev:api\" \"bun run dev:web\"",
  "dev:web": "next dev --hostname 127.0.0.1 --port 3010",
  "dev:api": "bun --watch server/index.ts",
  "dev:text-style": "cd services/psdlike-text-style && uv run uvicorn app.main:app --host 127.0.0.1 --port 4120",
  "check": "bun run typecheck && bun run test",
  "build": "next build"
}
```

所以当前主链路是三进程开发态：

```text
Next web: 127.0.0.1:3010
Elysia API: 127.0.0.1:4110
PSD-like text style service: 127.0.0.1:4120
```

当前根依赖很克制：`elysia`、`@elysiajs/cors`、`next`、`react`、`konva/react-konva`、`sharp`、`bun:sqlite`、`vitest`、`typescript`。这说明主业务不是 Python/Go monolith，而是 TS 主链路加一个 Python style-only 辅助服务。

## 当前主业务：API 入口

`server/index.ts` 是当前唯一主 API 入口。它初始化 SQLite，并暴露以下 API：

```text
GET    /api/health
GET    /api/ai-slice-settings
GET    /api/projects
POST   /api/projects
GET    /api/projects/:projectId
PATCH  /api/projects/:projectId
DELETE /api/projects/:projectId
POST   /api/projects/:projectId/pages
PATCH  /api/projects/:projectId/pages/order
PATCH  /api/projects/:projectId/pages/:pageId
POST   /api/projects/:projectId/pages/:pageId/replace
DELETE /api/projects/:projectId/pages/:pageId
POST   /api/projects/:projectId/pages/:pageId/ai-boxes
GET    /api/projects/:projectId/pages/:pageId/source
PUT    /api/projects/:projectId/slices
GET    /api/projects/:projectId/slices/:sliceId/preview.png
POST   /api/projects/:projectId/export-assets
GET    /api/projects/:projectId/assets.zip
POST   /api/projects/:projectId/export-project
POST   /api/projects/:projectId/pages/:pageId/export-project
GET    /api/projects/:projectId/pages/:pageId/project.zip
GET    /api/projects/:projectId/project.zip
```

关键事实：

1. 当前 API 没有接入旧 `/api/pencil/slice-projects/*`。
2. 当前 API 没有接入旧 `/api/draft-preview`。
3. 当前 API 已有单页导出：`POST /api/projects/:projectId/pages/:pageId/export-project`。
4. 当前 API 的 export idle timeout 是 255 秒，说明导出被认为是长任务，但它仍是同步请求，不是后台任务队列。

## 当前主业务：数据模型

`server/db.ts` 用 `bun:sqlite`。真实表只有三张：

```text
projects(id, name, created_at, updated_at, page_count, slice_count)
pages(id, project_id, page_index, original_name, display_name, original_path, width, height, created_at)
slices(id, project_id, page_id, slice_index, name, kind, cut_mode, x, y, width, height, created_at, updated_at)
```

约束：

```text
slices.kind CHECK kind IN ('image')
slices.cut_mode CHECK cut_mode IN ('rect', 'subject', 'card')
```

代码里 `SliceRow.cut_mode` 还允许 `"shape"`，但初始化迁移会把 `"shape"` 转成 `"subject"`。这是一个小的类型残留，不是当前业务能力。

`server/projects.ts` 是项目和页面的事实源：

1. 新建项目创建 `storage/projects/<projectId>/originals` 和 `exports`。
2. 上传页面统一转 PNG，写入 `storage/projects/<projectId>/originals/<pageId>.png`。
3. 保存 slices 时先删除项目下所有旧 slices，再按 payload 全量写入。
4. `replacePage` 会删除该 page 的 slices。
5. `deleteProject` 直接删 SQLite row，并删除项目文件夹。

这里没有多用户、权限、租户、审计、软删除。当前代码是本地单用户产品形态。

## 当前主业务：共享合同

`shared/types.ts` 定义的真实业务对象很小：

```ts
export type SliceKind = "image";
export type CutMode = "rect" | "subject" | "card";
export type BBox = { x: number; y: number; width: number; height: number };
export type SliceRecord = {
  id: string;
  projectId: string;
  pageId: string;
  sliceIndex: number;
  name: string;
  kind: "image";
  cutMode: CutMode;
  bbox: BBox;
  selected: true;
};
```

结论：当前产品不是“全自动重建完整设计稿”的合同，而是“原图页面 + 用户/AI 确认切片 + OCR 可编辑文字 + Pencil 导出”。

## 当前主业务：前端真实流程

`components/workspace/ProjectWorkspace.tsx` 是项目列表页：

1. 读取 `/api/projects`。
2. 创建项目后跳转 `/projects/<id>/review`。
3. 支持项目重命名、删除、搜索、过滤、网格/列表视图。

`components/review/ReviewWorkbench.tsx` 只是动态加载壳，实际逻辑在 `ReviewWorkbenchClient.tsx`：

1. 持有项目详情、页面、当前页、当前切片、画布工具、缩放/平移、撤销栈、保存状态。
2. 上传图片后调用 `POST /api/projects/:projectId/pages`。
3. 画框/编辑切片后通过 800ms debounce 调 `PUT /api/projects/:projectId/slices`。
4. 支持页面重命名、页面排序、页面替换、删除页面。
5. 支持 AI 识别框：调用 `POST /api/projects/:projectId/pages/:pageId/ai-boxes`。
6. 支持 assets.zip 导出、全项目 project.zip 导出、单页 project.zip 导出。
7. 语言目前在 Review 页面内部用 `localStorage` 保存 `zh/en`，不是全局 i18n 框架。

小代码问题：`components/review/ReviewWorkbench.tsx` 顶部有重复的 `"use client";`，不影响运行，但说明这块有编辑残留。

## 当前主业务：AI 切图建议

`server/ai-slice-boxes/index.ts` 的真实流程：

```text
getProjectDetail + getPageOriginalPath
-> sharp 读取尺寸
-> generateTiles(tileCount, overlap)
-> prepareTileImage(maxSide, jpegQuality)
-> callAiSliceProvider / callAiSliceOverviewProvider
-> parseAiBoxResponse
-> mapTileBoxToPage
-> filterAiBoxes(existingSlices, bounds, maxBoxes)
```

配置在 `server/config.ts`：

```text
SLICE_STUDIO_AI_SLICE_PROVIDER: openai_responses | disabled
SLICE_STUDIO_AI_SLICE_BASE_URL
SLICE_STUDIO_AI_SLICE_API_KEY
SLICE_STUDIO_AI_SLICE_MODEL
SLICE_STUDIO_AI_SLICE_WIRE_API: responses | chat_completions
SLICE_STUDIO_AI_SLICE_TILE_COUNT
SLICE_STUDIO_AI_SLICE_TILE_OVERLAP
SLICE_STUDIO_AI_SLICE_BATCH_CONCURRENCY
```

这部分的设计方向是对的：AI boxes 是 transient suggestion，不直接绕过 `saveSlices`。最终导出真相仍是 SQLite 里的 saved slices。

## 当前主业务：Pencil 导出链路

`server/pencil-exporter.ts` 是当前项目导出的核心：

```text
exportPencilProject(projectId)
  -> getProjectDetail(projectId)
  -> exportPencilDetail(...)
  -> buildPencilDocument(...)
  -> write project.zip

exportPencilProjectPage(projectId, pageId)
  -> getProjectDetail(projectId)
  -> filter 单页
  -> exportPencilDetail(...)
```

`buildPencilDocument` 对每页做：

```text
读取原图
-> cropSliceToPng 每个已保存 slice
-> preparePencilSliceImage 处理 rect/subject/card 的可见 placement
-> runOcr(originalBuffer)
-> reconstructTextLayers(...)
-> buildPageRenderPlan(...)
-> createRemainderPng(...)
-> 生成 frame children:
   z=0 remainder image
   z=1..n text nodes
   z=after text slices
-> design.pen + manifest.json + project.json
```

当前关键事实：

1. `controlSurfaceNode` 函数仍存在。
2. `ControlSurfaceLayer` / `SurfaceKnockout` 类型仍存在。
3. 但 `buildPageRenderPlan` 现在固定 `controlSurfaces = []`，`surfaceKnockouts = []`。
4. 也就是说：当前主链路默认不再矢量化按钮/控件背景，只保留栅格背景，叠加可编辑文本。

这和最近修复方向一致：控件背景不要硬矢量化，避免渐变按钮、阴影、圆角被错误重建。

## 当前主业务：文字识别与文字重影处理

文字链路由四块组成：

```text
server/text-ocr.ts
server/m29-text-locator.ts
server/text-reconstruction.ts
server/pencil-package.ts
```

`text-reconstruction.ts` 的实际流程：

```text
if OCR ok:
  raw = sharp(image).ensureAlpha().raw()
  locateTextLinesWithM29(...)
  refineWithLocalForeground(...)
  classifyTextOwnership(...)
  detectTextOwnerSurface(...)
  resolveTextStyles(...)
  makeTextLayer(...)
  harmonizeTextRows(...)
return TextReconstruction
```

`m29-text-locator.ts` 的事实：

1. 默认 `textBBoxSource = "m29_ocr_hybrid"`。
2. 默认 `physicalEvidenceProvider = "ts_m29_physical_evidence"`。
3. 如果配置为 `go_m29extract`，会调用 `archive/legacy-code/services/backend-go/bin/m29extract`。
4. TS M29 当前只用于文本 bbox 辅助；`isTextLikePrimitive` 明确排除 `surface_region` 和 `image_region`。

`render-plan-builder.ts` 的文字 knockout 事实：

1. 对普通文本输出 `{ bbox: layer.knockoutBBox, provenance: "ocr_text" }`。
2. 对 `filled_control_surface` 上的短标签输出 `raster_owned_control_text`：

```ts
{
  bbox: intersection(layer.knockoutBBox, ownerSurface.bbox),
  clipShape: rounded owner surface,
  foregroundColor: layer.color,
  paintPadding: 0,
  provenance: "raster_owned_control_text"
}
```

`pencil-package.ts` 的 `createRemainderPng` 当前顺序：

```text
paintTextForeground(textKnockouts)
clearSurfaceOwnership(surfaceKnockouts)   // 当前主 plan 为空
clearAlphaBySliceMask / clearAlphaRect(slices)
```

这里的名字 `paintTextForeground` 容易误导。它做的不是把文字画出来，而是在 remainder 上把原栅格文字像素用估计背景色覆盖掉，避免后续 Pencil text 叠上去后出现重影。

这就是现在“不要做矢量控件背景，只处理文字重影”的实际代码落点。

## 当前主业务：PSD-like text style 微服务

当前仍在主链路里的 Python 服务是 `services/psdlike-text-style`，不是 archive 里的旧 PSD-like 全链路。

服务入口：

```text
services/psdlike-text-style/app/main.py
-> FastAPI(title="Slice Studio PSD-like Text Style")
-> include_router(api.router)
```

API：

```text
GET  /health
POST /api/text-style-batch
```

`/api/text-style-batch` 输入整页图片和一组 `{ text, bbox, ownerSurface }`，输出：

```text
fontSize
fontWeight
fontFamily
color
lineHeight
textAlign
measured width/height
source="psdlike"
```

TS 调用端 `server/psdlike-text-style.ts` 是 fail-open：

1. provider 不是 `psdlike` 时返回 `null`。
2. HTTP 非 ok 返回 `null`。
3. 结果数量或字段不对返回 `null`。
4. 异常返回 `null`。

结论：这个服务现在只影响文本样式估计，不参与图层所有权、不参与 remainder 裁剪、不参与 slice 所有权。这个边界是正确的。

## 当前主业务：测试事实

根目录当前测试集中在：

```text
tests/pencil-exporter.test.ts
tests/m29-physical-evidence.test.ts
tests/shape-cutout.test.ts
tests/bbox.test.ts
tests/manifest.test.ts
tests/zip.test.ts
tests/ai-slice-boxes.test.ts
tests/psdlike-text-style.test.ts
tests/validation.test.ts
```

`tests/pencil-exporter.test.ts` 很大，覆盖了当前最关键的导出行为：

1. slice 从 remainder 挖掉。
2. OCR 文本区域从 remainder 中被覆盖，slice alpha 行为不变。
3. filled control surface 默认保持 raster-owned。
4. raster-owned control label 只清 glyph，不重绘控件外部。
5. `buildPageRenderPlan` 当前不生成 `controlSurfaces` 和 `surfaceKnockouts`。
6. 仍保留旧 surface owner-band cleanup 的测试，这和当前 builder 默认不输出 surface knockout 之间存在历史残留。

测试缺口：

1. `ProjectWorkspace` 和 `ReviewWorkbenchClient` 没有前端交互测试覆盖。
2. 真实 OCR/AI provider 依赖外部服务，单测只能覆盖解析、fallback、过滤。
3. 导出质量最终还是需要真实 `.pen` 打开验收；单测不能证明视觉交付质量。

## archive 代码：总分层

`archive/legacy-code` 不是一个系统，而是至少十条历史路线：

```text
Figma-design                         第一代 JS/Figma 插件 + 手动切图 server
figma-plugin                         workspace 化 Figma 插件
packages/dsl-schema                  DSL 合同、校验、修复、Draft Runtime 类型
packages/image-to-figma-renderer     DSL -> Figma Adapter 渲染器
backend                              Python FastAPI upload-preview + M29 实验矩阵
services/backend-python              OmniParser/VLM/OCR -> Draft Runtime DSL 服务
services/backend-go                  Go M29 + Draft compile/exportdsl
services/pencil-go                   Go Pencil project server/exporter
services/pencil-python-backend       Python M29/PSD-like/hybrid -> Pencil project
services/pencil-asset-backend        YOLO/image icon asset handoff
services/pencil-handoff-studio       UI slicing + Pencil handoff studio
services/psdlike-python              旧 PSD-like full pipeline
```

这些路线之间有复用关系，但不是一个干净分层。它们的入口、存储、路由、artifact 合同彼此不同。

## archive：Figma-design

关键文件：

```text
archive/legacy-code/Figma-design/project-server.js
archive/legacy-code/Figma-design/code.js
archive/legacy-code/Figma-design/server.js
archive/legacy-code/Figma-design/ui.html
archive/legacy-code/Figma-design/manual-slice.html
```

`project-server.js` 是老的本地手动切图 server：

1. 用 Node `http` 手写服务。
2. 用 `node:sqlite` 的 `DatabaseSync`。
3. 表结构也是 `projects/pages/slices`，但旧 `slices.kind` 允许 `image/icon`，没有当前的 `cut_mode`。
4. API 路由是 `/api/projects/*`，和当前根 API 形态相似，但实现完全独立。
5. 只支持 `export-assets` 和 `assets.zip`，没有当前 Pencil project export。

`code.js` 是老 Figma 插件主脚本：

1. `create-ui-asset-screen`：生成 UI 参考图和切图资产。
2. `create-editable-design-screen`：按 manifest 生成可编辑实验图层。
3. 直接操作 Figma API，不经过当前 Pencil `.pen`。

判断：这是当前 Slice Studio 的祖先，但现在只剩参考价值。不能复活为主链路。

## archive：figma-plugin + renderer + DSL

关键文件：

```text
archive/legacy-code/figma-plugin/src/main.ts
archive/legacy-code/figma-plugin/src/apiClient.ts
archive/legacy-code/packages/dsl-schema/src/types.ts
archive/legacy-code/packages/dsl-schema/src/validator.ts
archive/legacy-code/packages/image-to-figma-renderer/src/renderDesign.ts
archive/legacy-code/packages/image-to-figma-renderer/src/renderDraftRuntimeDesign.ts
```

`figma-plugin/src/main.ts` 的事实流程：

```text
render-sample
  -> renderDesign(mobileHome DSL)

render-uploaded-png-draft
  -> uploadPngDraftPreview(file)
  -> poll getDraftPreviewTask
  -> getDraftPreviewDsl
  -> renderDraftRuntimeDesign
```

`apiClient.ts` 固定 API base：

```ts
export const API_BASE_URL = "http://localhost:8000/api";
```

也就是说旧插件绑定的是旧 Python backend `/api/draft-preview`，不是当前 Elysia API。

`dsl-schema` 的合同：

```text
DesignDSL(version=0.1, taskId, page, assets, root)
DSLElement(type=frame/group/text/shape/image/icon/line)
layout(x,y,width,height)
style(fill,color,opacity,radius,stroke,shadow,font...)
```

`image-to-figma-renderer` 的事实：

1. `renderDesign` 先 `validateDSL`，再 `normalizeDSL`，再递归 render frame。
2. `renderDraftRuntimeDesign` 支持 Draft Runtime DSL，按 z 排序 children，创建 Figma frame/text/shape/image。
3. 文本渲染会 `loadFont`、`setTextStyle`、`setTextAutoResize("NONE")`、`applyLayout`。

判断：DSL 是一个有价值的中间合同，但它服务的是 Figma 插件路径。当前产品主链路是 Pencil `.pen`，如果未来重启 Figma 直导，可以借 DSL 的 contract/validator/renderer 思路；现在不应该把它插到当前导出里。

## archive：backend Python 大实验区

关键入口：

```text
archive/legacy-code/backend/app/main.py
```

它创建 FastAPI：

```text
include_router(health)
include_router(upload_preview)
include_router(tasks)
include_router(assets)
mount /files/uploads
mount /files/assets
```

这个 backend 下的真实代码模块很多，包括：

```text
visual_primitive
source_ui_physical_graph
visual_object_candidate_audit
text_masked_media_audit
stable_design_cluster
symbol_fragment_grouping
image_math
ownership_conservation
plan_materializer
m29_evidence_contract
png_tools
text_visual_ownership_gate
visual_evidence_normalization
layout_energy_report
design_token_report
hierarchy_candidate_report
media_internal_decomposition
text_aware_visual_object_refinement
upload_preview
```

判断：这是 M29/M30 系列研究和审计工具的沉淀，代码量大，测试多，但不是当前运行面。里面最值得抽取的是：

1. `image_math/*` 的基础图像工具。
2. `text_visual_ownership_gate` 的文字/视觉归属决策。
3. `plan_materializer` 的声明式 materialization 思路。
4. `source_ui_physical_graph` 的物理图层关系。

不应该抽取的是它的 FastAPI route/task/storage 体系，因为当前 Elysia/SQLite 已经有自己的项目模型。

## archive：services/backend-python

入口：

```text
archive/legacy-code/services/backend-python/app/main.py
```

真实路由：

```text
GET  /api/health
POST /api/draft-preview
POST /api/draft-preview/batch
GET  /api/draft-preview/{task_id}
GET  /api/draft-preview/{task_id}/dsl
GET  /api/draft-preview/{task_id}/assets/{asset_name}
```

流程：

```text
PNG upload
-> task_id
-> asyncio task
-> Pipeline(config).run(input_path, output_dir, task_id)
-> draft_runtime.dsl.v1_0.json
```

依赖包含 `onnxruntime`、`openai`、`Pillow`、`numpy`。描述是 OmniParser + VLM + OCR pipeline。

判断：这是旧 Figma plugin 的后端，不是当前主链路。可参考点是“异步任务 + DSL artifact”，但不要直接接入当前 Slice Studio。

## archive：services/backend-go

入口代码主要在 Go 包：

```text
archive/legacy-code/services/backend-go/internal/m29/pipeline/pipeline.go
archive/legacy-code/services/backend-go/internal/draft/assemble/assemble.go
archive/legacy-code/services/backend-go/internal/draft/exportdsl/export.go
```

Go M29 `Run` 的事实流程：

```text
read PNG
optional OCR
estimate background
build textMask from OCR blocks
build foreground mask
connected components
emit OCR text_region primitives
detectSurfaceCandidates
emit surface_region primitives
classify connected components
emit image/text/symbol primitives
detectInternalRasterCropCandidates
build relations
write m29_physical_evidence.v1.json
write debug_overlay.png / preview_sheet.png
```

Go Draft `assemble.Build` 的事实：

1. 总是加 hidden reference image。
2. `surface_region_token/layer_background_token/line_token` 变 shape layer。
3. `raster_region_token/symbol_cluster_token` 变 raster layer + asset。
4. `text_token` 变 text layer。
5. 合并 vision detector candidates。
6. 做 suppression：vision 覆盖 M29、重复 visible owners。
7. 生成 groups。

判断：Go M29 是历史上更完整的物理证据源，当前 TS M29 是简化版。当前代码已经保留 `go_m29extract` fallback 配置，但默认不用。未来只有当 TS M29 的证据不足时，才应该把 Go M29 作为工具或参考，而不是把 Go server 接回主业务。

## archive：services/pencil-go

`archive/legacy-code/services/pencil-go/internal/server/server.go` 真实路由：

```text
GET  /api/health
POST /api/pencil/projects
GET  /api/pencil/projects/{taskId}
GET  /api/pencil/projects/{taskId}/manifest
GET  /api/pencil/projects/{taskId}/download.zip
```

它的模式是：

```text
multipart PNG upload
-> task
-> goroutine runTask
-> project.Export(...)
-> manifest + zip
```

判断：这是 Go 版 Pencil 项目导出服务。它比当前 Elysia 同步导出更像正式后台任务，但它是另一套任务存储和导出合同。可参考“异步导出任务”的产品形态，不适合直接复活。

## archive：services/pencil-python-backend

入口：

```text
archive/legacy-code/services/pencil-python-backend/app/main.py
```

路由：

```text
health
projects
slice_projects
```

其中 `routes/slice_projects.py` 暴露：

```text
POST   /api/pencil/slice-projects
GET    /api/pencil/slice-projects/new
GET    /api/pencil/slice-projects/workspace
GET    /api/pencil/slice-projects
GET    /api/pencil/slice-projects/{project_id}
PUT    /api/pencil/slice-projects/{project_id}
POST   /api/pencil/slice-projects/{project_id}/clone
DELETE /api/pencil/slice-projects/{project_id}
GET    /api/pencil/slice-projects/{project_id}/review
GET    /api/pencil/slice-projects/{project_id}/candidates
GET    /api/pencil/slice-projects/{project_id}/source/{page_id}
GET    /api/pencil/slice-projects/{project_id}/manual-slices
GET    /api/pencil/slice-projects/{project_id}/review-state
PUT    /api/pencil/slice-projects/{project_id}/review-state
PUT    /api/pencil/slice-projects/{project_id}/manual-slices
POST   /api/pencil/slice-projects/{project_id}/export
POST   /api/pencil/slice-projects/{project_id}/export-preview
GET    /api/pencil/slice-projects/{project_id}/download.zip
GET    /api/pencil/slice-projects/{project_id}/selected-assets.zip
```

`project_builder.py` 是这个旧服务的核心：

```text
export_project
-> selected_modes
-> build_boundary_artifact(m29 | psdlike | hybrid)
-> export_single_page
-> compute_layout
-> build_mode_project
-> create_project_zip
```

`exporter/single_page.py` 是最有价值的历史实现。它定义三种模式：

```text
clean-editable:
  cleaned crops + visible editable OCR text

visual-fidelity:
  crop-only visual handoff; OCR text remains bitmap

visual-ocr:
  visual-friendly cleaned bitmap layers + visible OCR text
```

它的 `build_production_document` 有清晰的图层分类：

```text
editable_shape_layers
crop_layers
editable_text_layers
text_decisions
dedupe_visible_crop_layers
copy_used_crop_to_visible_assets(... enable_text_knockout ...)
make_text_node
```

`copy_used_crop_to_visible_assets` 的关键策略：

```text
如果 crop layer 不是 text/art/visual_text region，
并且 enable_text_knockout，
就 build_text_mask_for_layer，
erase_masked_pixels，
生成 *.clean.png。
```

这说明旧 Python 链路解决文字重影的基本思想不是“矢量化所有控件背景”，而是：

```text
文字变可编辑
旧栅格文字从底下 crop/remainder 里消失
其他视觉背景尽量保持栅格
```

这和当前最新主链路方向一致。

## archive：services/pencil-asset-backend

入口：

```text
archive/legacy-code/services/pencil-asset-backend/app/main.py
```

路由在 `routes/asset_projects.py`，核心是：

```text
POST create_asset_project
GET list/get/review/source/evidence/candidates/manual-slices/review-state
PUT review-state/manual-slices
POST export-preview
POST export
GET download.zip / selected-assets.zip
```

依赖包括 `ultralytics`，创建项目时强制检查 YOLO model：

```python
if state.settings.yolo_model is None:
    raise HTTPException(... "YOLO UI model is required")
```

判断：这条路线面向 image/icon asset handoff，适合参考 AI/YOLO 候选框流程，不适合作为当前默认后端。

## archive：services/pencil-handoff-studio

入口：

```text
archive/legacy-code/services/pencil-handoff-studio/app/main.py
```

它也是 FastAPI + StaticFiles，路由在 `routes/handoff_projects.py`。`create_handoff_project` 支持：

```text
projectName
includeOcr
includeBasicElements
multi-file upload
initialize_project
export_handoff_project
```

判断：这是 Pencil handoff 的另一代 Python 产品壳，比 asset-backend 更宽，但仍是旧项目模型。它和当前 Slice Studio 的概念相似，但不是当前代码事实。

## archive：services/psdlike-python

依赖：

```text
FastAPI
httpx
uvicorn
python-multipart
Pillow
numpy
```

CodeGraph 找到的关键函数：

```text
archive/legacy-code/services/psdlike-python/app/core/masks.py
build_text_knockout_mask(rgb, blocks)
```

实现策略：

```text
对每个 OCR block:
  clamp bbox
  region = rgb[box]
  bg = estimate_text_background_for_box
  diff = ||region - bg||
  threshold = percentile(diff)
  coverage 自适应调整
  小覆盖时 dilate
  过大覆盖时收紧
  mask[box] |= local
```

这和当前 `pencil-package.ts` 的 `paintTextForeground` 目标一致：识别原栅格字像素并用背景覆盖。但旧 PSD-like 是 numpy mask，当前 TS 是逐像素 foreground/background 判断。

判断：这部分适合对当前文字重影算法做对照测试，但不应该恢复为全链路服务。当前已经有更小的 `services/psdlike-text-style` style-only 服务，边界更干净。

## 当前主链路与 archive 的差异表

| 维度 | 当前主链路 | archive 主要路线 |
|---|---|---|
| 产品入口 | Next `/projects` 与 `/review` | Figma 插件、本地 HTML、FastAPI/Go server |
| API | Elysia `server/index.ts` | 多套 `/api/draft-preview`、`/api/pencil/*`、`/api/asset-projects/*` |
| 状态真相 | SQLite `projects/pages/slices` | 各服务自带 JSON/storage/task/db |
| 图像真相 | 上传原图 + saved SliceRecord | M29 primitives、DSL nodes、manual slices、task artifacts |
| 导出目标 | `assets.zip`、`project.zip/design.pen` | Figma direct render、Draft Runtime DSL、Pencil ZIP |
| 文本策略 | OCR + M29 bbox + style-only + raster text knockout | M29 text primitives、PSD-like masks、多模式 crop/text |
| 控件背景 | 默认 raster-owned，不矢量化 | 多路线尝试 shape/surface/vector |
| 运行复杂度 | 1 TS API + 1 Next + 1 style service | 多语言多服务多合同 |

主矛盾不是“archive 没用”。主矛盾是：archive 里有很多解决过局部问题的算法，但它们绑定在旧产品形态和旧合同里；当前产品需要稳定交付，就必须只抽取最小算法事实，不能把旧系统整体拉回主链路。

## 可复用资产清单

可以复用或参考：

1. `pencil-python-backend/app/exporter/single_page.py`
   - 三模式导出设计。
   - `clean-editable` 的生产保证。
   - text decision 记录方式。
   - crop layer 与 editable text layer 分离。

2. `services/psdlike-python/app/core/masks.py`
   - `build_text_knockout_mask` 的 percentile + coverage 自适应思想。
   - 可以用于对照当前 TS `paintTextForeground` 的误擦/漏擦场景。

3. `services/backend-go/internal/m29/pipeline`
   - `surface_region`、`image_region`、connected components、relations。
   - 适合作为未来 surface mask evidence 的来源。

4. `packages/dsl-schema`
   - schema/validator/repair 的中间合同思想。
   - 如果未来要 Figma 直导，应该先定义当前 Pencil-like/RenderPlan 合同，再考虑 DSL 转换。

5. `packages/image-to-figma-renderer`
   - Figma Adapter 抽象。
   - Draft Runtime DSL 的 render order、font load、fixed text layout。

不建议复用：

1. 旧 FastAPI/Go server 路由。
2. 旧 storage/task 模型。
3. 旧 Figma-design 的手写 JS server。
4. 旧全量 PSD-like pipeline 作为当前主链路。
5. 旧“尽量矢量化控件背景”的默认策略。

## 当前主业务的真实风险

1. **archive 运行产物污染严重。**

   代码树里存在 `.venv`、`__pycache__`、`.pytest_cache`、`storage/*.db`、大量历史 `.pen/.zip`。这不一定都被 Git 跟踪，但它们会干扰搜索、打包、CodeGraph、上下文判断。后续整理应该先查 `git ls-files`，只处理未跟踪/生成产物，不能误删有价值样本。

2. **当前 `render-plan.ts` 保留了已经不默认使用的 control surface 合同。**

   `SurfaceKnockout`、`ControlSurfaceLayer`、`clearSurfaceOwnership`、相关 tests 还在，但 `buildPageRenderPlan` 固定输出空数组。这是历史残留。它不是 bug，但会误导后续开发，以为“控件矢量化”仍是主策略。

3. **文字重影算法现在是启发式，不是严格 mask。**

   当前 `paintTextForeground` 通过背景估计和前景色距离覆盖旧文字。它比矢量化控件背景稳，但仍可能在渐变、纹理、低对比文字上漏擦或误擦。旧 PSD-like 的 mask 算法可以作为对照测试，不应直接整套迁移。

4. **前端关键工作台没有自动化覆盖。**

   `ReviewWorkbenchClient` 承担上传、保存、画框、排序、AI、导出、撤销，但没有前端测试。当前产品如果继续做交付，至少需要几个 Playwright 级 smoke。

5. **导出仍是同步请求。**

   Elysia idle timeout 拉到 255 秒只是缓解，不是正式任务队列。页面多、OCR 慢、AI 慢时，用户体验和失败恢复都会差。旧 Go/Python 服务都有 task 模型，可以参考，但不要直接复活。

6. **当前没有认证/租户/权限。**

   这不是从 docs 判断，而是 API、DB schema、前端请求都没有 user/session/project owner 字段。上线成多用户产品前必须补。

7. **`services/psdlike-text-style` 目录里有 `.venv`。**

   主业务目录下有运行环境产物，会污染仓库分析和备份。至少应该确认 `.gitignore` 覆盖。

8. **当前 AI provider 默认配置需要实测。**

   `server/config.ts` 默认 `SLICE_STUDIO_AI_SLICE_MODEL` 是 `gpt-5.5`，默认 API 是 OpenAI responses。代码本身支持 `chat_completions` base URL，这对 OpenRouter 集成有帮助，但真实可用性必须用 key 实测。

## 对后续整理的建议

### 第一优先级：明确主链路边界

当前主链路应该只认这些目录：

```text
app/
components/
server/
shared/
tests/
services/psdlike-text-style/
package.json
tsconfig.json
next.config.ts
vitest.config.ts
```

`archive/legacy-code` 只作为 reference，不参与默认 build/dev/test。

### 第二优先级：清理生成产物，不清理历史源代码

建议先生成 tracked/untracked 清单：

```bash
git ls-files archive/legacy-code | sort
git status --ignored --short archive/legacy-code services/psdlike-text-style
```

然后只处理确定的生成产物类型：

```text
__pycache__/
.pytest_cache/
.venv/
storage/*.db
storage/**/*.pen
storage/**/*.zip
dist/
repomix-output.xml
```

注意：不要直接删除历史样本图片/JSON，很多可能是回归证据。

### 第三优先级：收敛当前 RenderPlan 命名

如果产品策略已经确定为“控件背景 raster-owned，文字可编辑”，应该考虑把当前合同命名得更诚实：

```text
TextKnockout 保留
SurfaceKnockout 标记为 legacy / experimental
ControlSurfaceLayer 默认不生成
render-plan-builder 不暴露看似会生成 surface 的假象
```

这不是急修，但能减少后续“又走回矢量化按钮”的概率。

### 第四优先级：把旧 Python text mask 思路变成测试样本，而不是微服务大改

正确方式：

1. 在当前 `tests/pencil-exporter.test.ts` 增加复杂背景/渐变按钮/低对比文字样本。
2. 用旧 `build_text_knockout_mask` 的测试思想设计 fixtures。
3. 当前 TS `paintTextForeground` 过不了再做最小改动。

不要一上来把旧 PSD-like full pipeline 接回主业务。

### 第五优先级：导出任务队列

如果项目要支持 30 张图、长图、OCR、AI，当前同步导出迟早会卡。旧 `pencil-go` 和 `backend-python` 的 task 模型可以参考，但当前实现最好仍在 Elysia/SQLite 内做：

```text
export_jobs table
POST export -> jobId
GET job status
GET job zip
后台 worker 或 Bun child task
```

这是正式上线前的工程化工作，不是当前视觉修复的一部分。

## 对旧 DSL 的判断

用户提到“之前 DSL 可能稳定”。从代码看，这个判断有一半对。

对的地方：

1. `dsl-schema` 有明确 schema、validator、repair。
2. `image-to-figma-renderer` 有 adapter 和递归渲染。
3. Draft Runtime DSL 的 z-order、固定文本框、asset resolve 这些概念确实比直接拼 Figma/Pencil 节点更稳定。

不对的地方：

1. 旧 DSL 绑定的是旧 `/draft-preview` 和旧 Figma plugin，不绑定当前 Elysia/SliceRecord/Pencil export。
2. 当前产品的核心真相是用户保存的 SliceRecord，不是全自动 DSL tree。
3. 如果现在把旧 DSL 插进来，会多一层转换，而且会重新引入“全页面自动重建”的复杂度。

实际建议：保留 DSL 作为未来 Figma 直导的候选中间层；当前 Pencil 导出继续走 `PageRenderPlan`，不要立刻切 DSL。

## 具体文件索引

当前主业务应优先看：

```text
server/index.ts
server/projects.ts
server/db.ts
server/pencil-exporter.ts
server/pencil-package.ts
server/render-plan.ts
server/render-plan-builder.ts
server/text-reconstruction.ts
server/m29-text-locator.ts
server/m29-physical-evidence/index.ts
server/ai-slice-boxes/index.ts
server/psdlike-text-style.ts
components/workspace/ProjectWorkspace.tsx
components/review/ReviewWorkbenchClient.tsx
shared/types.ts
tests/pencil-exporter.test.ts
```

archive 中最值得作为参考的代码：

```text
archive/legacy-code/services/pencil-python-backend/app/exporter/single_page.py
archive/legacy-code/services/pencil-python-backend/app/project_builder.py
archive/legacy-code/services/backend-go/internal/m29/pipeline/pipeline.go
archive/legacy-code/services/backend-go/internal/m29/pipeline/surface.go
archive/legacy-code/services/backend-go/internal/draft/assemble/assemble.go
archive/legacy-code/services/psdlike-python/app/core/masks.py
archive/legacy-code/packages/dsl-schema/src/types.ts
archive/legacy-code/packages/dsl-schema/src/validator.ts
archive/legacy-code/packages/image-to-figma-renderer/src/renderDraftRuntimeDesign.ts
archive/legacy-code/figma-plugin/src/main.ts
```

archive 中不建议继续作为主链路入口的代码：

```text
archive/legacy-code/Figma-design/project-server.js
archive/legacy-code/Figma-design/code.js
archive/legacy-code/backend/app/main.py
archive/legacy-code/services/backend-python/app/main.py
archive/legacy-code/services/pencil-go/internal/server/server.go
archive/legacy-code/services/pencil-asset-backend/app/main.py
archive/legacy-code/services/pencil-handoff-studio/app/main.py
archive/legacy-code/services/pencil-python-backend/app/main.py
```

## 结论

当前仓库不是“没有主线”。主线已经很明确：Slice Studio 根目录 TS 产品。真正的问题是历史代码太多，而且很多旧代码都解决过局部难题，容易诱导后续开发在不同体系之间跳来跳去。

后续最稳的策略：

```text
主业务继续保持 root TS/Elysia/Next/Pencil export
archive 只当算法证据库
有用算法先变成当前 tests/fixtures
测试证明有效后，再用当前合同重写
不要复活旧 server、旧 storage、旧 plugin 作为主线
```

这也是最近文字问题的教训：旧 Python 链路里真正有价值的不是“整套服务”，而是“文字可编辑时必须清掉底层旧 glyph，同时控件背景尽量保持栅格”的原则。当前最新主链路已经回到这个方向。
