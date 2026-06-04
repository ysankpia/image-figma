# 后端架构

当前分支的可交付后端主线是 `services/pencil-python-backend` assisted slice workspace。它接收 1..N 张图片，生成 `candidates.v1.json`，由用户确认 `manual_slices.v1.json`，再导出 `project.zip` 和 `selected-assets.zip`。

本文件下面记录的是历史/延后 Go Draft backend 架构。只有明确恢复 `/api/draft-preview` 自动可编辑稿路线时，才把它作为实现参考。

## Runtime Surface

当前产品 API：

```text
GET  /api/health
POST /api/draft-preview
GET  /api/draft-preview/{taskId}
GET  /api/draft-preview/{taskId}/dsl
GET  /api/draft-preview/{taskId}/assets/{assetId}.png
GET  /api/draft-preview/{taskId}/artifacts
```

旧 `/api/codia-preview` 和 Python `/api/upload-preview` 不是当前 Draft runtime。

## Processing Pipeline

```text
receive multipart PNG
-> validate MIME, PNG signature, size, and dimensions
-> save task source.png
-> create task status=queued stage=draft_queued
-> OCR
-> Go M29 physical evidence
-> optional vision detector
-> optional vision review
-> Draft assembly
   -> TextLayer
   -> RasterLayer
   -> ShapeLayer
   -> GroupLayer
   -> hidden ReferenceImage
-> Draft asset crop/write
-> Draft validation
-> Draft Runtime DSL export
-> mark task completed
```

## Backend Packages

Target package layout:

```text
internal/app      HTTP, task, storage
internal/image    geometry, pngio, crop, color, mask
internal/m29      physical evidence
internal/vision   detector, provider, prompt, review
internal/draft    contract, assemble, asset, group, exportdsl, validate, report
internal/eval     Codia/reference metrics only
```

## Ownership Boundaries

`internal/app` must not contain ownership heuristics.

`internal/image` must not contain UI roles or provider logic.

`internal/m29` must not emit final Draft layers.

`internal/vision` must not emit final Draft layers or DSL.

`internal/draft/assemble` is the layer ownership authority.

`internal/draft/exportdsl` is mechanical conversion only.

`internal/eval` may read Codia golden. Product generation must not import `internal/eval`.

## Failure Policy

M29 and Draft assembly/export failures fail the task. Asset write failure fails the task. Optional vision failure writes a fallback artifact and continues unless explicitly required.

The server must recover from panics inside task goroutines and mark tasks failed. A task must not remain permanently `running`.

## Legacy Paths

These paths are historical on this branch:

```text
Go Codia Beta compiler
Codia assembly/control/tree/emitter
DSL v0.2 Codia Runtime as product target
Python FastAPI M29 preview as product runtime
M29 Direct compare
legacy M30 materialization
M31-M39/M39.1 downstream experiments
ONNX proposer
```

Do not restore them as product-generation paths.
