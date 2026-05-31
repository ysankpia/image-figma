# 093 Editable Draft Layer Pipeline Rebuild

- 状态：active
- 创建日期：2026-05-31
- 分支：`feat/editable-draft-layer-pipeline`
- 负责人：Codex

## Goal

把当前 Go 后端从 Codia Beta / Codia-like tree 实验路径破坏性重构为 Editable Draft 产品主线：

```text
PNG
-> OCR + M29 physical evidence + optional vision detector/review
-> Editable Layer Graph
-> Draft Runtime DSL
-> Renderer
-> Figma editable draft
```

目标不是复刻官方 Codia JSON，也不是继续修补 `assembly/control/tree/emitter`。目标是输出稳定、可审计、可编辑、可由插件渲染的 Figma 草稿。

## First Principles

真实产品目标：

```text
PNG -> editable Figma draft
```

主合同：

```text
editable_layer_graph.v1.json
```

核心不变量：

```text
one visible foreground pixel -> one visible owner
```

这意味着：

- 原图不能作为 visible full-page backing。
- TextLayer 必须在同区域 RasterLayer/ShapeLayer 上方。
- RasterLayer 必须有可解析 asset。
- ShapeLayer 不应携带前景文字像素。
- Codia golden 只能用于 eval，不能进入 generation。

## Scope

包含：

- 冻结当前 Codia Beta 分支为 baseline。
- 新建 `feat/editable-draft-layer-pipeline` 分支。
- 重置 `AGENTS.md` 和 docs 入口，让当前事实源指向 Draft 主线。
- 新增 Go 包边界：`internal/app`、`internal/image`、`internal/vision`、`internal/draft`、`internal/eval`。
- 定义 `editable_layer_graph.v1` 合同。
- 迁移/重建 provider-neutral vision detector/review 边界。
- 新增 Draft asset、validation、exportdsl、server 路径。
- 插件接 `/api/draft-preview`。
- 将 Codia Beta 生成路径降级为 legacy/eval，后续删除或归档。

不包含：

- 不追官方 Codia JSON byte-for-byte。
- 不让 VLM 直接生成最终 DSL/Figma tree。
- 不把 Button/ListView/BottomNavigation/ActionBar 作为第一版结构 authority。
- 不接 Auto Layout、Component、Instance、variables、vectorization。
- 不兼容旧 `/api/codia-preview` 作为产品主线。
- 不在 Python `/api/upload-preview` 上修 Draft runtime。
- 不使用样本名、品牌、文案、固定 bbox、固定坐标、固定屏幕尺寸特化。

## Target Go Architecture

```text
services/backend-go/
  cmd/
    draftserver/
    draftcompile/
    draftdetect/
    drafteval/
    m29extract/
    m29trace/

  internal/
    app/
      server/
      storage/
      task/

    image/
      crop/
      geometry/
      pngio/
      color/
      mask/

    m29/
      primitive/
      evidence/
      relation/
      visualtree/
      ocr/
      pipeline/

    vision/
      detector/
      provider/
      prompt/
      review/

    draft/
      contract/
      assemble/
      asset/
      group/
      exportdsl/
      validate/
      report/

    eval/
      codia/
      metrics/
```

New generation packages must not use `codia`, `tree`, `control`, `leaf`, `emitter`, or `compiler` as product-generation names.

## Stage Plan

### Stage 0: Branch Isolation

Actions:

- Create `baseline/codia-beta-current`.
- Create `feat/editable-draft-layer-pipeline`.
- Confirm clean worktree.

Validation:

```bash
git status --short --branch
git diff --check
```

### Stage 1: Documentation And Contract Reset

Actions:

- Rewrite `AGENTS.md` around Draft mainline.
- Rewrite `docs/index.md` as a short current-state map.
- Add Draft architecture docs:
  - `docs/architecture/runtime.md`
  - `docs/architecture/draft-layer-graph.md`
  - `docs/architecture/vision-provider.md`
  - `docs/architecture/m29-physical-evidence.md`
  - `docs/architecture/plugin-rendering.md`
- Add engineering docs:
  - `docs/engineering/current-code-map.md`
  - `docs/engineering/validation.md`
  - `docs/engineering/anti-specialization.md`
  - `docs/engineering/artifact-policy.md`
- Move old Codia detector plan out of active.

Validation:

```bash
git diff --check
rg -n "Codia Beta development and debugging mainline|/api/codia-preview.*formal|Generate Beta.*current" AGENTS.md docs/index.md docs/architecture docs/engineering
```

Acceptance:

- Current docs start from Draft, not Codia Beta or Python upload-preview.
- Codia is described as eval/reference only.
- Draft graph contract and hard invariants are documented.

### Stage 2: Go Package Skeleton

Actions:

- Add focused package skeletons under `internal/app`, `internal/image`, `internal/vision`, `internal/draft`, and `internal/eval`.
- Add initial `editable_layer_graph.v1` Go types.
- Add validation stubs for asset refs, text z-order, and visible reference/backing invariants.

Validation:

```bash
cd services/backend-go
go test ./...
```

Acceptance:

- New packages compile.
- No generation package imports `internal/eval`.

### Stage 3: Vision Detector Migration And Concurrency

Actions:

- Move provider-neutral detector code from `internal/codia/detector` to `internal/vision/detector`.
- Add bounded pass concurrency.
- Rename config from `CODIA_UI_DETECTOR_*` to `VISION_*`.
- Keep provider/baseUrl/model/apiKey configurable.

Validation:

```bash
cd services/backend-go
go test ./internal/vision/... ./cmd/draftdetect
```

Acceptance:

- Multi-pass calls can run concurrently with deterministic post-sort.
- Optional vision failure produces fallback artifact and does not fail Draft by default.

### Stage 4: Editable Layer Assembly

Actions:

- Build Draft assembly from OCR, M29 evidence, detector candidates, and optional review decisions.
- Emit `TextLayer`, `RasterLayer`, `ShapeLayer`, `GroupLayer`, and hidden `ReferenceImage`.
- Preserve decision provenance for emit/consume/suppress/refine.

Validation:

```bash
cd services/backend-go
go test ./internal/draft/...
```

Acceptance:

- TextLayer above same-region Raster/Shape.
- No visible full-page backing.
- RasterLayer requires asset source.
- Ordinary OCR text stays editable.
- Compact supported image/icon/avatar/cover evidence can become RasterLayer.

### Stage 5: Draft Assets And Runtime DSL Export

Actions:

- Crop/write RasterLayer assets.
- Write `asset_manifest.json`.
- Export `draft_runtime.dsl.v1.json`.
- Keep exporter mechanical; no ownership decisions in exporter.

Validation:

```bash
cd services/backend-go
go test ./internal/draft/asset ./internal/draft/exportdsl ./internal/draft/validate
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
```

Acceptance:

- Completed Draft DSL has resolvable image assets.
- Renderer receives text/raster/shape/group order without needing ownership fixes.

### Stage 6: Draft Server And Plugin Route

Actions:

- Add `cmd/draftserver`.
- Add `/api/draft-preview` task flow.
- Wire plugin to Draft route and remove/retire `Generate Beta` as the main action.

Validation:

```bash
cd services/backend-go
go test ./internal/app/... ./cmd/draftserver
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm --filter @image-figma/figma-plugin run build
```

Acceptance:

- Plugin can upload a PNG, poll task, fetch DSL/assets, and render Draft.
- Plugin image asset warnings are zero for successful tasks.

### Stage 7: Real Sample Validation

Actions:

- Run 018, 022, Lizhi, and Xianyu through Draft pipeline.
- Inspect artifacts and plugin/render warnings.

Acceptance:

- asset missing = 0.
- plugin image load failed = 0.
- visible full-page backing = 0.
- TextLayer covered by RasterLayer = 0.
- unauthorized large sibling overlap = 0.
- major visible text remains editable.
- compact image/icon/avatar/cover layers are draggable RasterLayers where supported.
- major regions are grouped for movement.

### Stage 8: Legacy Cleanup

Actions:

- Remove or archive Codia generation path:
  - `assembly`
  - `control`
  - `tree`
  - `emitter`
  - `compiler`
  - `canvasexport`
  - `leaf`
  - `ir`
  - old DSL 0.2 Codia exporter
- Keep Codia comparison under `internal/eval/codia` only.
- Clean docs so `Start Here` and current runtime docs no longer route to legacy.

Validation:

```bash
rg -n "internal/codia|Generate Beta|/api/codia-preview|codia_runtime" services/backend-go packages figma-plugin docs
cd services/backend-go && go test ./...
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm --filter @image-figma/figma-plugin run build
git diff --check
```

Allowed remaining Codia references:

- `docs/reference/codia-samples`
- `internal/eval/codia`
- historical archive docs

## Acceptance

This plan is complete only when:

- The product runtime is `/api/draft-preview`, not `/api/codia-preview`.
- Go backend has focused Draft package boundaries.
- `editable_layer_graph.v1.json` and `draft_runtime.dsl.v1.json` are generated for real samples.
- Plugin can render Draft output with zero image asset warnings for successful tasks.
- Codia golden is eval-only and not imported by generation packages.
- Old Codia generation code is removed or isolated outside the product runtime.
- Current docs and `AGENTS.md` route future work to Draft, not Python mainline or Codia Beta.

## Validation Summary

Required before final close:

```bash
git diff --check
cd services/backend-go && go test ./...
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm --filter @image-figma/figma-plugin run build
```

Real-flow validation must include at least one successful plugin request and the four sample artifact checks listed in Stage 7.

## Risks

- Large deletion may break old tests before the new Draft route is complete. Stage commits must keep rollback points.
- Renderer may still expect old DSL shape. Exporter and renderer contract changes must be staged together.
- Vision provider instability must not block M29/OCR fallback.
- If cleanup is delayed, stale Codia docs/packages may keep confusing future agents. Stage 8 must not be skipped.

## Learning Backflow

If a rule, invariant, or validation check prevents a regression, move it from chat/local notes into:

- `docs/engineering/anti-specialization.md`
- `docs/engineering/validation.md`
- `docs/architecture/draft-layer-graph.md`
- a focused test or script
