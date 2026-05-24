# Image-to-Figma Roadmap

- 状态：active
- 日期：2026-05-24

## Purpose

本文档固定当前路线，避免后续工作在黑色主题、搜索框、轮播图、历史 M30、M29 Direct compare、组件化和代码生成之间来回跳。

当前路线不是“先组件化”，也不是“继续给每张样图打补丁”。正确主线是：

```text
像素拓扑与归属
-> replay plan
-> plan-driven visible layers
-> 通用关系图
-> 稳定设计簇
-> layout semantics
-> component/instance
```

第一性原理边界：

```text
PNG 像素是输入真相源。
M29 的第一职责是把扁平 PNG 拆成像素集合、集合关系和 owner。
M29.5 replay plan 是可见 materialization 的订单。
模型、Figma MCP、UIC/Codia schema 都只能提供候选或参考，不能直接成为内部真值源。
```

硬不变量：

```text
同一块 source foreground evidence pixel / replay foreground pixel 只能有一个 replay owner。
```

这条不变量优先级高于所有下游 grouping、unit promotion、layout semantics 和 componentization。它不禁止 Figma layer bbox 重叠；背景 shape 可以和 child text/image/icon 在空间上重叠，因为它们拥有不同 source evidence。

## Current Mainline

当前产品主链：

```text
Figma Plugin
-> POST /api/upload-preview
-> OCR
-> raw M29 primitive graph
-> M29.2 source ownership
-> M29.3 region relation
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> M29 plan-driven materializer
-> GET /api/tasks/{taskId}/dsl
-> Renderer
-> Figma Canvas
```

`/api/upload-preview` 是当前正式上传入口。`/api/tasks/{taskId}/dsl` 是唯一正式设计稿出口。

当前已经下线：

```text
M29 Direct compare product endpoint
legacy M30 materializer product path
M31-M39 downstream runtime
ONNX proposer runtime
pre-M29 upload/debug chain
```

## Current M29 Contracts

M29 当前已经形成这些合同：

```text
raw M29:
  source PNG + OCR -> primitive graph, support backgrounds, shape geometry fit

M29.2:
  primitive graph -> sourceObjects with visualKind / pixelOwner / replayDecision

M29.3:
  pure bbox kernel and relation graph

M29.4:
  weak structural evidence only

M29.5:
  finalReplayAction, targetRole, cleanupTargets, z-order, dedupe, node budget

M29 materializer:
  consume M29.5 plan, create DSL, copy/crop raster assets, execute authorized cleanup
```

M29.4 weak clusters do not create components, groups, Auto Layout, Figma Component/Instance, or materialization permission.

## What To Improve Next

### 1. Stabilize Current M29 MVP

Highest leverage work:

- keep adding contract regression cases for real failures.
- test dark, light, and mixed screenshots with fallback off.
- verify raster/media preservation covers charts, photos, avatars, textured cards, and complex foreground.
- verify simple low-texture supports still stay as editable shapes.
- keep cleanup authorization tied to M29.5 plan.

Do not patch output by text content, language, color name, theme, image filename, bbox, or business category.

### 2. Code Slimming

Long files are now a real maintenance risk. Refactor only with behavior-preserving tests:

```text
visual_primitive_graph.py
source_ui_physical_graph.py
m29_plan_materializer.py
upload_preview_pipeline.py
```

Suggested split order:

1. raw M29 bbox/mask/support/geometry/artifact helpers.
2. M29.2 media/text/icon/shape ownership classifiers.
3. M29 materializer node appenders and cleanup executors.
4. pipeline orchestration, asset publishing, and task state handling.

Do not mix naming cleanup with algorithm changes. Product surface cleanup should stay mechanical and separately tested.

### 3. Historical Code Pruning

Current runtime no longer depends on M29.0.x or M30 product materialization. Remaining historical modules and tests should be handled by a separate pruning plan:

```text
classify as still-useful test utility, offline diagnostic, or removable historical code
remove only after reachability scan and focused tests
do not delete png_tools, OCR, storage, database, route, DSL, or renderer primitives
```

### 4. Layout And Component Work

Do not start componentization until owner/relation/replay/materialization are stable on diverse images.

Future layout/component work needs explicit contracts:

```text
Pixel Ownership Conservation:
  every replayed bbox and cleanup action must explain pixel ownership.

Graph Isomorphism:
  repeated unit matching must compare node labels, edge labels, normalized geometry, and slot differences.

Layout Energy:
  row/column/grid/masonry should be chosen by measurable error, not visual impression.

Materialization Permission:
  define which graph/layout evidence may create group/container, and which evidence stays report-only.
```

## Non-Goals For The Next Phase

Do not use the next phase for:

```text
Auto Layout
Figma Component/Instance
frontend code generation
global optimization
Codia adapter
batch upload
quality dashboard
account/payment/quota
```

Those are not blocked forever. They are blocked until M29 source truth is stable enough that higher-level optimization is not just arranging wrong objects more neatly.
