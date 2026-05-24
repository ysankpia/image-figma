# 测试策略

当前测试目标是保护产品主线和 M29 Direct compare variant：

```text
Figma plugin
-> /api/upload-m30-preview
-> OCR
-> raw M29 / M29.2 / M29.3 / M29.4 / M29.5
-> M29 Direct compare variant
-> legacy M29.0.x bridge
-> M30 DSL v0.1
-> Renderer
```

M30.2.2 已删除 pre-M29 legacy upload chain。M29 backend downstream pruning 已删除 M31-M39/M39.1 和 ONNX proposer runtime。测试不再要求这些旧 routes、env、modules 或 reports 存在。

## Validation Focus

v0.1 重点验证：

- DSL schema 稳定。
- Renderer 可消费 DSL v0.1。
- 后端当前 API 可创建任务、更新状态、返回 M30 DSL。
- M29/M30 evidence chain 不污染 visible DSL children。
- 插件默认上传走 `/api/upload-m30-preview`。
- 插件 compare mode 上传一次后分别拉取 M29 Direct variant 和主线 DSL。
- M29.5 replay plan 可被写出并被 M29 Direct replay 消费。
- 本地 M30 image asset URL 可由 renderer fetch。
- 本地 M29 Direct image asset URL 可由 renderer fetch。
- 删除的 downstream routes/modules/env 不再出现在 backend runtime。

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
- compare mode completed 后调用 `/api/tasks/{taskId}/m29-direct-dsl` 和 `/api/tasks/{taskId}/dsl`。
- compare mode 把第二份 DSL root 平移 `page.width + 80`。
- renderer writes M30 DSL to Figma。
- UI 能显示 upload、processing、fetching DSL、rendering、success/failure 状态。

## Backend Current Chain

Focused current-chain command:

```bash
cd backend
uv run pytest \
  tests/test_visual_primitive_graph.py \
  tests/test_source_ui_physical_graph.py \
  tests/test_region_relation_kernel.py \
  tests/test_region_relation_graph_report.py \
  tests/test_stable_design_cluster.py \
  tests/test_m29_replay_plan.py \
  tests/test_m29_direct_replay.py \
  tests/test_evidence_grounded_dsl_materialization.py \
  tests/test_m30_upload_pipeline.py \
  tests/test_routes_tasks.py \
  tests/test_config_env.py \
  tests/test_png_tools.py \
  tests/test_upload_flow.py \
  -q
```

Required backend coverage:

- `GET /api/health` succeeds.
- `POST /api/upload` returns 404.
- old task debug endpoints return 404.
- `POST /api/upload-m30-preview` accepts PNG and creates a processing task.
- invalid MIME, invalid PNG, unreadable dimensions, and too-large file are rejected.
- completed task returns M30 DSL from `m30_materialized_dsl.json`.
- completed task writes M29.5 replay plan to `m29_5/replay_plan.json`.
- completed task returns M29 Direct experiment DSL from `m29_direct_replay_dsl.json` through `/api/tasks/{taskId}/m29-direct-dsl`.
- unfinished task returns `DSL_NOT_READY`.
- missing M29 Direct variant returns `M29_DIRECT_DSL_NOT_FOUND`.
- `GET /api/tasks/{taskId}/m30-materialization` returns report summary and stage timings.
- M30 materialization report returns text editability decisions and preserved graphic text items.
- M30 image assets are published under `/files/assets/{taskId}/m30/...`.
- M29 Direct assets are published under `/files/assets/{taskId}/m29_direct/...`.
- OCR provider failures fail the task and do not create fake completed DSL.
- CORS covers `/api/upload-m30-preview`.
- New upload tasks do not create removed downstream directories or stages.

## M29/M30 Evidence Chain

Focused command:

```bash
cd backend
uv run pytest \
  tests/test_visual_primitive_graph.py \
  tests/test_symbol_fragment_grouping.py \
  tests/test_text_masked_media_audit.py \
  tests/test_visual_evidence_normalization.py \
  tests/test_text_visual_ownership_gate.py \
  tests/test_visual_object_candidate_audit.py \
  tests/test_text_aware_visual_object_refinement.py \
  tests/test_mixed_symbol_text_conflict_audit.py \
  tests/test_evidence_grounded_dsl_materialization.py -q
```

Required evidence coverage:

- M29 bboxes come from existing source evidence.
- M29.1 lineage is preserved only where allowed.
- mixed/future/audit-only evidence remains audit-only.
- M29.0.7 ownership routing prevents text-owned evidence from forming visual objects.
- M29.0.5 formal visual assets are created only for safe visual members.
- M30 materializes only trusted textMembers, safe shapeCandidates, and safe visualAssets.
- M30.6 materializes only low-overlap large accepted image assets with recovered raw M29 lineage.
- M30.6 does not relax text-overlap policy for ordinary icons or small visual assets.
- M30.7 removes editable text pixels only from M30 copied media assets, never from M29.0.5 source assets.
- M30.7 materializes only large `partially_separated` composite media with existing `combinedAssetPath`; it does not split internal art text.
- OCR text evidence is not dropped before M29; graphic text is preserved by M30 editability decision instead.
- `graphic_text_preserve_in_fallback` does not generate `m30_text_member` and does not enter fallback erasure.
- plain horizontal UI text still generates `m30_text_member`.
- M30 does not create new bboxes.
- M30 does not rewrite M29 JSON.
- M30 does not emit DSL `icon` type.
- M36 samples editable text foreground color from source pixels or records a contrast/default fallback.

## M29 Direct Replay Compare Mode

M29 Direct replay contract coverage is tracked in [m29-contract-regression-matrix.md](m29-contract-regression-matrix.md). New M29 Direct、ownership、relation、cluster、replay plan 或 cleanup changes must either map to an existing matrix case or add a new case before implementation.

Focused command:

```bash
cd backend
uv run pytest tests/test_source_ui_physical_graph.py tests/test_m29_replay_plan.py tests/test_m29_direct_replay.py tests/test_m30_upload_pipeline.py tests/test_routes_tasks.py -q
```

Required coverage:

- M29.2 classifies high-confidence UI OCR text as editable.
- M29.2 preserves OCR text inside textured media as raster.
- M29.2 merges adjacent symbol fragments into one `raster_icon`.
- M29.2 only replays stable UI shapes and keeps complex blur/shadow diagnostic-only.
- M29 low-contrast support regions are detected from physical evidence on light and dark themes.
- M29.2 consumes `low_contrast_support` and `text_support_background` only after raw M29 records physical support evidence.
- M29 low-contrast support regions must have finite outer-ring evidence; page-edge open bands are rejected.
- M29.2 must route small high-texture/high-color circle or ellipse foreground to raster icon/fallback instead of pure shape replay.
- M29.2 media regions prevent internal fragments from becoming separate replay layers.
- OCR text suppresses high-overlap M29 raster primitive.
- M29.5 and M29 Direct preserve visible replay order: shape/support/background, then image, then icon, then text.
- `preserve_in_parent_raster` does not create visible nodes and does not erase fallback pixels.
- blocked/unknown primitives remain report-only.
- fallback erases replayed bboxes without mutating source PNG or M29 assets.
- node budget prevents flat layer explosion.
- M29 Direct root/base assets use `m29_direct_*` namespace.
- upload pipeline writes `m29_5_replay_plan`, `m29_direct_replay`, and `m29_direct_asset_publish` timings.
- `/api/tasks/{taskId}/m29-direct-dsl` returns DSL/report after completion.
- M29 Direct failures do not block the mainline `/api/tasks/{taskId}/dsl`.
- `/api/tasks/{taskId}/dsl` remains the current legacy M30 mainline DSL.

## Static Pruning Checks

For backend pruning phases, run:

```bash
rg -n "M31_UPLOAD|M38_HIERARCHY|M39_|m31-reconstruction|m39-boundary-classification|m39-1-unit-structure-readiness" backend/app backend/tests
```

```bash
rg -n "reconstruction_ui_tree|hierarchy_readiness|hierarchy_materialization|content_chrome_classification|unit_structure_readiness|onnx_box_proposer|pre_ocr_symbol_lineage_audit|member_boundary_quality_audit|residual_mixed_boundary_review" backend/app backend/tests backend/scripts
```

Both commands should return no matches.

## Removed Test Areas

Tests for removed runtime are historical and must not be restored just because completed plans or ADRs mention them:

```text
M31 reconstruction tree
M37 hierarchy readiness
M38 hierarchy materialization
M39 content/chrome classification
M39.1 unit structure readiness
ONNX proposer
M29.1.1 pre-OCR lineage audit
M29.0.6 member boundary quality audit
M29.0.3.2 residual mixed boundary review
```
