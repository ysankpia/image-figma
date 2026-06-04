# Draft Runtime

Draft runtime 是历史/延后自动化路线。当前分支的可交付产品主线是
`services/pencil-python-backend` assisted slice workspace：

```text
images -> candidates.v1.json -> manual_slices.v1.json -> project.zip + selected-assets.zip
```

本文件保留 Draft 路线的接口和合同说明，只有在显式恢复 Go Draft 时才作为实现参考。

## Request Flow

```text
POST /api/draft-preview
  -> create task
  -> save source PNG
  -> run OCR
  -> run M29 physical evidence
  -> optionally run vision detector
  -> optionally run vision review
  -> assemble Editable Layer Graph
  -> validate Draft contracts
  -> crop/write assets
  -> export Draft Runtime DSL
  -> mark task completed

GET /api/draft-preview/{taskId}
GET /api/draft-preview/{taskId}/dsl
GET /api/draft-preview/{taskId}/assets/{assetId}.png
```

## Task States

```text
queued
running
completed
failed
```

Server task execution must recover from panic and mark the task failed with a useful error. A task must not remain permanently `running` because a goroutine crashed.

## Artifact Layout

Per task:

```text
source.png
ocr.json
m29/m29_physical_evidence.v1.json
vision/ui_detector_candidates.v1.json
vision/ui_candidate_review.v1.json
draft/editable_layer_graph.v1.json
draft/draft_validation_report.md
draft/draft_runtime.dsl.v1.json
assets/asset_manifest.json
assets/*.png
logs/task_report.md
```

Vision artifacts are optional. Draft artifacts are required for completed tasks.

## Runtime Ownership

`internal/app` owns HTTP, task state, storage, and response shape.

`internal/m29` owns physical evidence extraction.

`internal/vision` owns model calls, prompt contracts, provider config, parse/normalization, pass concurrency, and review decisions.

`internal/draft` owns layer graph assembly, asset cropping, grouping, validation, reporting, and DSL export.

`packages/image-to-figma-renderer` owns Figma node creation from DSL.

## Failure Policy

OCR failure may fail the task when OCR is configured as required. M29 failure fails the task. Draft validation failure fails the task unless the failing check is explicitly marked warning-only.

Vision detector/review failure does not fail the task by default. The server writes a fallback artifact and continues with OCR/M29 evidence unless the request explicitly requires vision.

Asset write failure fails the task. A completed task must not contain unresolved RasterLayer asset references.

## Non-Runtime Boundaries

Codia eval may read completed Draft artifacts and golden samples. Runtime generation must not read Codia golden data.

Python `/api/upload-preview` remains historical/reference. It must not be called by Draft runtime.
