# 测试策略

当前测试目标是保护产品主线：

```text
Figma plugin
-> /api/upload-m30-preview
-> OCR + M29 + M30
-> DSL v0.1
-> Renderer
```

M30.2.2 已删除 pre-M29 legacy upload chain。测试不再要求旧 `/api/upload` 或旧 M8-M28 debug endpoints 可恢复。

## Validation Focus

v0.1 重点验证：

- DSL schema 稳定。
- Renderer 可消费 DSL v0.1。
- 后端当前 API 可创建任务、更新状态、返回 M30 DSL。
- M29/M30 evidence chain 不污染 visible DSL children。
- 插件默认上传走 `/api/upload-m30-preview`。
- 本地 M30 image asset URL 可由 renderer fetch。

## DSL Schema

```bash
pnpm --filter @image-figma/dsl-schema run typecheck
pnpm --filter @image-figma/dsl-schema run test
```

必须覆盖：

- 合法 DSL 通过。
- 缺必填字段失败。
- 非法 element type 失败。
- image assetId 不存在失败。
- normalize/repair 只做安全修复。

## Renderer

```bash
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
```

必须覆盖：

- frame/text/shape/image/line 可渲染。
- fallback 图片可显示。
- 原图参考层默认隐藏。
- 单元素失败不拖垮整页。
- 图片加载失败产生 warning。
- M30 `m30_text_cover` 普通 shape 可渲染。
- M30 visual assets 作为 image node 渲染。

## Figma Plugin

```bash
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm --filter @image-figma/figma-plugin run build
```

必须覆盖：

- 默认上传调用 `/api/upload-m30-preview`。
- 上传后轮询 `/api/tasks/{taskId}`。
- completed 后调用 `/api/tasks/{taskId}/dsl`。
- renderer writes M30 DSL to Figma。
- UI 能显示 upload、processing、fetching DSL、rendering、success/failure 状态。

## Backend API

Focused current-chain command:

```bash
cd backend
uv run pytest \
  tests/test_m30_upload_pipeline.py \
  tests/test_evidence_grounded_dsl_materialization.py \
  tests/test_upload_flow.py \
  tests/test_config_env.py \
  tests/test_assets.py \
  tests/test_baidu_ocr.py -q
```

Required backend coverage:

- `GET /api/health` succeeds.
- `POST /api/upload` returns 404.
- old task debug endpoints return 404.
- `POST /api/upload-m30-preview` accepts PNG and creates a processing task.
- invalid MIME, invalid PNG, unreadable dimensions, and too-large file are rejected.
- completed task returns M30 DSL from `m30_materialized_dsl.json`.
- unfinished task returns `DSL_NOT_READY`.
- `GET /api/tasks/{taskId}/m30-materialization` returns report summary and stage timings.
- `GET /api/tasks/{taskId}/m31-reconstruction` returns reconstruction summary and stage timings.
- default upload creates M31 diagnostics after M29.
- M31 optional failure does not block M30 DSL when strict mode is off.
- M31 failure blocks the task at `m31_reconstruction` when strict mode is on.
- M30 image assets are published under `/files/assets/{taskId}/m30/...`.
- OCR provider failures fail the task and do not create fake completed DSL.
- CORS covers `/api/upload-m30-preview`.

## M29/M30 Evidence Chain

Current-chain command:

```bash
cd backend
uv run pytest \
  tests/test_visual_primitive_graph.py \
  tests/test_symbol_fragment_grouping.py \
  tests/test_pre_ocr_symbol_lineage_audit.py \
  tests/test_text_masked_media_audit.py \
  tests/test_visual_evidence_normalization.py \
  tests/test_text_visual_ownership_gate.py \
  tests/test_visual_object_candidate_audit.py \
  tests/test_text_aware_visual_object_refinement.py \
  tests/test_member_boundary_quality_audit.py \
  tests/test_mixed_symbol_text_conflict_audit.py \
  tests/test_residual_mixed_boundary_review.py \
  tests/test_evidence_grounded_dsl_materialization.py -q
```

Required evidence coverage:

- M29 bboxes come from existing source evidence.
- M29.1 lineage is preserved only where allowed.
- mixed/future/audit-only evidence remains audit-only.
- M29.0.7 ownership routing prevents text-owned evidence from forming visual objects.
- M29.0.5 formal visual assets are created only for safe visual members.
- M30 materializes only trusted textMembers, safe shapeCandidates, and safe visualAssets.
- M30 does not create new bboxes.
- M30 does not rewrite M29 JSON.
- M30 does not emit DSL `icon` type.
- M30.2 text cover uses existing text bbox and conservative background sampling.

## M31 Reconstruction UI Tree

M31 focused command:

```bash
cd backend
uv run pytest tests/test_reconstruction_ui_tree.py -q
```

Required M31 coverage:

- source PNG, OCR JSON, and M29 `nodes.json` load successfully.
- every M29 node becomes a primitive ref.
- each primitive ref is owned by exactly one reconstruction unit or assigned to exactly one review bucket.
- root does not contain primitive leaves.
- container-like M29 shapes can own inner primitive refs.
- row-aligned primitive refs can form media/text reconstruction units.
- same-size/same-spacing unit candidates can form repeated groups.
- every emitted reconstruction unit has a fallback crop asset.
- fallback crop bbox stays inside source image bounds.
- review bucket reasons use generic terms.
- business/page-specific forbidden terms are absent from M31 tree/report.
- `createdDetectionBBoxCount = 0`.
- `permissionViolationCount = 0`.
- M31 does not rewrite source M29 JSON.
- M31 upload diagnostics do not change M30 DSL, Renderer behavior, or plugin contract.
- production upload profile skips M31 overlay; development upload profile writes it.

## Static Guards

After M30.2.2, active backend source and tests must not reference the deleted legacy runtime surface:

```bash
rg "LEGACY_PRE_M29_UPLOAD_ENABLED|legacy_pre_m29_upload_enabled|legacy_router|routes/upload|legacy_tasks" \
  backend/app backend/tests
```

Expected: no results.

Deleted module names should not appear as imports or active module references in `backend/app`, `backend/scripts`, or `backend/tests`. Domain vocabulary inside M29 evidence, such as icon-like visual kind strings, is allowed when it is not importing or calling a removed module.

## Full Validation

```bash
cd backend
uv run pytest -q
```

```bash
pnpm run check
git diff --check
git status --short
```

## Manual Smoke

```bash
cd backend
M30_PREVIEW_PROFILE=production uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then upload 1 to 3 PNGs from the Figma plugin.

Acceptance:

- task reaches `completed`.
- `/api/tasks/{taskId}/dsl` returns M30 materialized DSL.
- Figma renders fallback plus editable M30 text/shape/image where evidence is safe.
- `/api/tasks/{taskId}/m30-materialization` shows stage timings.
- `/api/upload` returns 404.
- old debug endpoints return 404.
