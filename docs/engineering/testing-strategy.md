# 测试策略

当前测试目标先保护 Codia Beta Go 链路：

```text
Figma plugin
-> Generate Beta
-> Go /api/codia-preview
-> OCR
-> Go M29 physical evidence
-> optional online UI detector
-> Codia assembly/control/tree/emitter
-> DSL v0.2 Codia Runtime
-> local crop asset endpoint
-> renderCodiaRuntimeDesign
```

保留的 Python/FastAPI preview 链路仍需测试，但它不是 Codia Beta 输出质量调试主线：

```text
Figma plugin Generate from PNG
-> /api/upload-preview
-> OCR
-> raw M29 / M29.2 / M29.3 / M29.4 / M29.5
-> M29 ownership conservation / M29.6 media internal decomposition / M29 transparent asset report / B-stage reports
-> M29 plan-driven materializer
-> DSL v0.1
-> Renderer
```

M30.2.2 已删除 pre-M29 legacy upload chain。M29 backend downstream pruning 已删除 M31-M39/M39.1 和 ONNX proposer runtime。本阶段已下线 M29 Direct compare 产品入口和 legacy M30 materialization 产品路径。测试不再要求这些旧 routes、env、modules 或 reports 存在。

## Validation Focus

v0.1 重点验证：

- DSL schema 稳定。
- Renderer 可消费 DSL v0.1。
- 后端当前 API 可创建任务、更新状态、返回 M29 plan-driven DSL。
- M29 evidence chain 不污染 visible DSL children。
- 插件 Beta 上传走 Go `/api/codia-preview`。
- 插件 Beta completed 后只调用 `/api/codia-preview/{taskId}/dsl`。
- 插件默认上传走保留的 Python `/api/upload-preview`。
- 插件 default completed 后只调用 `/api/tasks/{taskId}/dsl`。
- M29.5 replay plan 可被写出并被 M29 materializer 消费。
- 本地 M29 image/raster/icon asset URL 可由 renderer fetch。
- fallback-off 深色/浅色/混合背景不依赖固定浅色默认背景。
- cleanup 权限全部可追溯到 M29.5 `cleanupTargets`。
- 删除的 compare/M30/downstream routes/modules/env 不再出现在 backend runtime。

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
- M29 materialized roles 作为普通 DSL element 渲染。
- Codia Runtime DSL v0.2 通过 `renderCodiaRuntimeDesign` 渲染 frame/group/text/shape/image。
- v0.2 ImageView 缺少 fetchable asset 时渲染占位并记录 warning，不阻断整页。

## Go Codia Runtime DSL 0.2

```bash
cd services/backend-go
go test ./internal/codia/dsl02 ./internal/codia/compiler ./internal/codia/server ./cmd/codiacompile ./cmd/codiaserver
```

必须覆盖：

- `codiacompile` 写出 `codia_runtime.dsl.v0_2.json`。
- `codiaserver` 接受 PNG 上传，运行 Go Codia compiler，并从 `/api/codia-preview/{taskId}/dsl` 返回 DSL 0.2。
- DSL 0.2 `type="image"` nodes have `image.assetId` when source bbox can be cropped.
- `codiaserver` serves `/api/codia-preview/{taskId}/assets/{assetId}.png` for local crop assets.
- With `CODIA_SERVER_DETECTOR_ENABLED=true`, `codiaserver` runs detector before compiler and passes candidates into assembly.
- DSL 0.2 顶层包含 `version="0.2"` 和 `kind="codia_runtime"`。
- Go Codia role/type/name/bbox 被机械翻译，不在 DSL 0.2 exporter 里重新做 ownership 仲裁。
- `ImageView` 没有 fetchable crop asset 时保留 provenance，交给 renderer 占位。

## Figma Plugin

```bash
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm --filter @image-figma/figma-plugin run build
```

必须覆盖：

- 默认上传调用 `/api/upload-preview`。
- 上传后轮询 `/api/tasks/{taskId}`。
- completed 后调用 `/api/tasks/{taskId}/dsl`。
- Beta 上传调用 `/api/codia-preview`。
- Beta 上传后轮询 `/api/codia-preview/{taskId}`。
- Beta completed 后调用 `/api/codia-preview/{taskId}/dsl` 并使用 `renderCodiaRuntimeDesign`。
- Beta Renderer receives `assetBaseUrl=/api/codia-preview/{taskId}` so Codia Runtime image assets do not fall back to `CODIA_RUNTIME_IMAGE_SOURCE_NOT_FOUND`.
- 不再调用 `/api/tasks/{taskId}/m29-direct-dsl` 或 `/api/tasks/{taskId}/m30-materialization`。
- renderer writes M29 plan-driven DSL to Figma。
- UI 能显示 upload、processing、fetching DSL、rendering、success/failure 状态。
- UI 不再出现 `Generate Compare` 或 mainline/direct 双画布选择。

## Backend Current Chain

Full backend command:

```bash
cd backend
uv run pytest -q
```

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
  tests/test_ownership_conservation.py \
  tests/test_media_internal_decomposition.py \
  tests/test_transparent_asset_report.py \
  tests/test_internal_source_promotion.py \
  tests/test_m29_plan_materializer.py \
  tests/test_upload_preview_pipeline.py \
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
- `POST /api/upload-preview` accepts PNG and creates a processing task with `stage=m29_queued`.
- invalid MIME, invalid PNG, unreadable dimensions, and too-large file are rejected.
- completed task returns M29 plan-driven DSL from `design.dsl.json`.
- completed task writes M29.5 replay plan to `m29_5/replay_plan.json`.
- completed task writes M29.6 media internal decomposition report to `m29_media_internal_decomposition/media_internal_decomposition_report.json`.
- completed task writes M29 transparent asset report to `m29_transparent_assets/transparent_asset_report.json`.
- completed task writes M29 internal source promotion report to `m29_internal_source_promotion/internal_source_promotion_report.json`.
- completed task returns M29 materialization report through `/api/tasks/{taskId}/materialization`.
- `/api/tasks/{taskId}/m29-direct-dsl` returns 404.
- `/api/tasks/{taskId}/m30-materialization` returns 404.
- unfinished task returns `DSL_NOT_READY`.
- M29 materialization failure fails the task and blocks `/dsl`.
- M29 image assets are published under `/files/assets/{taskId}/m29/...`.
- OCR provider failures fail the task and do not create fake completed DSL.
- CORS covers `/api/upload-preview`.
- New upload tasks do not create removed M29 Direct, M29.0.x, M30, or downstream directories/stages.

## M29 Evidence And Materialization Chain

Required evidence coverage:

- M29 bboxes come from existing source evidence.
- M29.2 classifies high-confidence UI OCR text as editable.
- M29.2 preserves OCR text inside textured media as raster.
- M29.2 routes large complex image-like regions to `preserve_raster` / `image_replay`.
- M29.2 merges adjacent symbol fragments into one `raster_icon`.
- M29.2 only replays stable UI shapes and keeps complex blur/shadow diagnostic-only.
- M29 low-contrast support regions are detected from physical evidence on light and dark themes.
- M29.2 consumes `low_contrast_support` and `text_support_background` only after raw M29 records physical support evidence.
- M29 low-contrast support regions must have finite outer-ring evidence; page-edge open bands are rejected.
- M29.2 must route small high-texture/high-color circle or ellipse foreground to raster icon/fallback instead of pure shape replay.
- M29.2 media regions prevent internal fragments from becoming separate replay layers.
- M29.6 reports composite `preserve_raster` media internal OCR/text masks/raw symbol or shape candidates and non-OCR foreground components without changing DSL, assets, replay plan, cleanup authorization, or materialization.
- M29.6 text masks prevent OCR glyph fragments from becoming internal icon candidates.
- M29.6 rejects large hero/texture fragments and separators as icon candidates unless generic evidence supports them.
- M29 transparent asset report only considers existing `raster_icon/icon_replay` source objects and execution-supported M29.6 `internal_icon_candidate` items.
- M29 transparent asset report rejects OCR-overlapping, unstable-background, execution-unsupported, high edge-alpha residue, or overly large candidates, and is not consumed directly by materializer.
- M29 internal source promotion writes promoted M29.2 source objects only for accepted, execution-supported M29.6 internal icon candidates with transparent asset allow.
- M29.5 keeps promoted internal icon overlay over its parent media only when source evidence links the icon to that parent media and transparent asset.
- materializer consumes transparent assets only after M29.5 has authorized the promoted icon replay.
- OCR text suppresses high-overlap M29 raster primitive.
- M29.5 preserves visible replay order: shape/support/background, then image, then icon, then text.
- `preserve_in_parent_raster` does not create visible nodes and does not erase fallback pixels.
- blocked/unknown primitives remain report-only unless M29.2 has generic source evidence to recover them as raster/icon/media.
- node budget prevents flat layer explosion.
- M29 plan materializer requires an M29.5 plan.
- M29 plan materializer only materializes plan-approved visible actions.
- M29 plan materializer samples root/page background from source PNG, not a fixed light default.
- fallback erasure is executed only with M29.5 fallback cleanup target.
- copied image asset text cleanup is executed only with M29.5 copied image asset cleanup target.
- copied image asset promoted-internal cleanup is executed only with M29.5 copied image asset cleanup target and transparent asset alpha mask.

## Static Pruning Checks

For current backend cleanup phases, run:

```bash
rg -n "m29-direct-dsl|m30-materialization|materialize_evidence_grounded_dsl|m29_direct_replay|evidence_grounded_dsl_materialization|mixed_symbol_text_conflict_audit" backend/app backend/tests backend/scripts figma-plugin/src
```

Expected: no production references. Negative assertions in tests are acceptable.

```bash
rg -n "M31_UPLOAD|M38_HIERARCHY|M39_|m31-reconstruction|m39-boundary-classification|m39-1-unit-structure-readiness" backend/app backend/tests
```

```bash
rg -n "reconstruction_ui_tree|hierarchy_readiness|hierarchy_materialization|content_chrome_classification|unit_structure_readiness|onnx_box_proposer|pre_ocr_symbol_lineage_audit|member_boundary_quality_audit|residual_mixed_boundary_review" backend/app backend/tests backend/scripts
```

Both downstream commands should return no matches.

## Removed Test Areas

Tests for removed runtime are historical and must not be restored just because completed plans or ADRs mention them:

```text
M29 Direct compare replay
legacy M30 evidence-grounded materialization
mixed symbol/text M30 guard
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
