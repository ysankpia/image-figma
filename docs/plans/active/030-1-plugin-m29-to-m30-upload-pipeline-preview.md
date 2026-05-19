# M30.1 Plugin M29-to-M30 Upload Pipeline Preview

- 状态：active
- 创建日期：2026-05-19
- 负责人：Codex

## Goal

M30.1 把插件上传默认路径切到当前正确主线：

```text
Figma plugin
-> POST /api/upload-m30-preview
-> OCR
-> M29 / M29.1 / M29.0.2 / M29.0.3.1 / M29.0.7 / M29.0.4 / M29.0.5
-> M30 materialized DSL
-> GET /api/tasks/{taskId}/dsl
-> Renderer writes DSL to Figma
```

这不是快速模式，也不是旧实验链路增强。目标是让产品入口真实消费 M29 可信 evidence 和 M30 DSL materialization。旧 `POST /api/upload` 保留为 legacy 对照，不删除、不改合同。

## Scope

包含：

- 新增 `POST /api/upload-m30-preview`。
- endpoint 先创建 task，再用 FastAPI `BackgroundTasks` 在同进程跑 OCR + M29 + M30。
- 新增 task 状态更新能力，支持 `processing`、`completed`、`failed`。
- 新增 M30.1 pipeline 模块，直接调用 app 层函数，不通过 shell 子进程。
- 成功后把 `dsl_results.dsl_path` 指向 `m30/m30_materialized_dsl.json`。
- 把 M30 DSL 中本地 asset url 改写成 `/files/assets/{taskId}/m30/...` 可访问 HTTP URL。
- 新增只读调试 endpoint `GET /api/tasks/{taskId}/m30-materialization`。
- 插件默认上传调用 M30 preview endpoint，并延长 task 轮询时间。

不包含：

- 不改 M29.0.3、M29.1.3、M29.0.7、M29.0.4、M29.0.5 分类合同。
- 不默认调用 M29.1.3、M29.0.3.2、M29.0.6。
- 不默认调用 M19-M25 legacy slice/icon harness、M24 visible fallback、M26-M28 perception/SAM。
- 不改 DSL schema。
- 不做 Auto Layout、Component、SVG/vectorization、text cover 或图标恢复。
- 不处理生产部署、安全鉴权、多用户并发或队列系统。

## Backend Contract

`POST /api/upload-m30-preview`：

```text
input:
  multipart PNG file

sync behavior:
  validate file
  save uploads/{taskId}/original.png
  create task status=processing stage=m30_queued
  enqueue background pipeline

response:
  existing UploadResult shape
```

Background pipeline stage root：

```text
backend/storage/m30_1_uploads/{taskId}/
  ocr/
  m29/
  m29_1/
  m29_0_2/
  m29_0_3/
  m29_0_7/
  m29_0_4/
  m29_0_5/
  m30/
```

Task stages use concrete stage names such as:

```text
ocr
m29
m29_1
m29_0_2
m29_0_3
m29_0_7
m29_0_4
m29_0_5
m30_materialization
m30_asset_publish
m30_completed
```

If a stage fails, the task becomes `failed`, an `error_logs` row is written, and `GET /api/tasks/{taskId}` exposes the failed stage and message.

## Pipeline Rules

M30.1 calls only:

```text
extract_ocr
extract_m29_visual_primitive_graph
extract_m291_symbol_fragment_grouping
extract_text_masked_media_audit
extract_visual_evidence_normalization
extract_text_visual_ownership_gate
extract_visual_object_candidate_audit
extract_text_aware_visual_object_refinement
materialize_evidence_grounded_dsl
```

M29.0.3 receives the M29.1 lineage document, so the M29.0.3.1 text-rejected lineage gate is active. M29.0.4 receives M29.0.7 ownership routing. M30 uses `bootstrap-dsl-from-m29` for uploaded images.

OCR failure is a task failure in M30.1. It must not create a fake completed M30 task with `textBoxes=0`.

## Artifact Profile

M30.1 uses `M30_PREVIEW_PROFILE` to separate development diagnostics from plugin runtime output:

```text
production   default for /api/upload-m30-preview
development  full local diagnostics
```

`production` keeps only OCR JSON, M29/M29.1/M29.0.2/M29.0.3/M29.0.7/M29.0.4/M29.0.5 structured JSON, M29.0.5 formal visual assets used by M30 image nodes, M30 DSL/report, published M30 renderer assets, error logs, and `stage_timings.json`. It skips overlay PNGs, preview sheets, review/contact sheets, example crops, and the M30 materialization preview PNG.

`development` preserves the previous full diagnostic output. M29/M30 single-stage scripts keep development-style output by default because their app-layer artifact flags default to `true`; only M30.1 production passes `false`.

This profile does not change OCR provider behavior, M29 classification/ownership rules, M30 DSL schema, renderer behavior, plugin API shape, or legacy `/api/upload`.

## Asset URL Rules

M30 materializer may emit local or relative asset URLs. Before saving the final DSL for plugin consumption, M30.1 must:

- copy every local DSL image asset into `backend/storage/assets/{taskId}/m30/`;
- rewrite `dsl.assets[].url` to `http://localhost:8000/files/assets/{taskId}/m30/...`;
- keep `source.assetId` unchanged;
- insert corresponding asset rows for debugging;
- not create new child crops from raw pixels.

This applies to the full-image fallback and any safe M30 visual assets.

## Plugin Contract

The plugin default upload action calls `/api/upload-m30-preview`, then keeps the existing flow:

```text
upload
-> poll task
-> fetch /api/tasks/{taskId}/dsl
-> renderDesign
```

Status text should describe the real pipeline without exposing old internal harness names:

```text
Uploading PNG.
Running OCR + M29 evidence pipeline.
Fetching M30 materialized design.
Writing design to Figma.
```

The sample render path stays unchanged.

## Acceptance

- `POST /api/upload-m30-preview` returns an existing UploadResult shape with a task id.
- Successful background pipeline marks task `completed`, `stage=m30_completed`.
- `GET /api/tasks/{taskId}/dsl` returns M30 DSL with `meta.qualityFlags` containing `m30_evidence_grounded_materialization`.
- M30 DSL preserves fallback and contains `m30_text_member` for OCR-rich images.
- M30 visible children do not include audit-only/mixed/future sources and never use DSL `type=icon`.
- DSL image asset URLs are fetchable through `/files/assets/{taskId}/m30/...`.
- `GET /api/tasks/{taskId}/m30-materialization` returns report summary, warnings, skipped items, and debug preview path.
- `GET /api/tasks/{taskId}/m30-materialization` returns `stageTimings` from `stage_timings.json`.
- `M30_PREVIEW_PROFILE=production` skips overlay/preview artifacts while preserving OCR, required JSON, formal assets, M30 DSL, and published renderer assets.
- `M30_PREVIEW_PROFILE=development` preserves full diagnostics for local debugging.
- OCR provider missing-token failure marks task failed and records the provider error.
- Legacy `POST /api/upload` tests continue to pass.
- Plugin default upload uses M30 preview endpoint.

## Validation

```bash
cd backend && uv run pytest tests/test_m30_upload_pipeline.py tests/test_upload_flow.py tests/test_evidence_grounded_dsl_materialization.py -q
```

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
git status --short
```

## Notes

- `backend/storage/**` remains diagnostic output and must not be committed.
- If single-image processing time becomes unacceptable, queueing is a separate stage. M30.1 deliberately starts with in-process background tasks.
