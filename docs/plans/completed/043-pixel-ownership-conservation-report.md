# M29 Pixel Ownership Conservation Report

- 状态：completed
- 创建日期：2026-05-25
- 负责人：未指定

## Goal

在当前 M29.2/M29.3.1/M29.5 已有局部 ownership、relation 和 replay 决策之上，新增一个全局、可审计、report-only 的 ownership conservation report。这个阶段只暴露风险，不改变 DSL、Figma 输出、replay plan、asset cleanup 或 materialization 行为。

## Scope

包含：

- 新增 `backend/app/ownership_conservation/` package。
- 在 `m29_5_replay_plan` 之后、`m29_materialization` 之前运行 `m29_ownership_conservation` stage。
- 写出 `storage/upload_previews/{taskId}/m29_ownership_conservation/ownership_conservation_report.json`。
- 汇总 source object claims、visible replay claims、cleanup claims、conflicts 和 warnings。
- 检查 visible overlap、missing/invalid copied image cleanup、non-visible item visible claim 等 conservation 风险。

不包含：

- 不修改 `/api/tasks/{taskId}/dsl` 或 `/api/tasks/{taskId}/materialization` response shape。
- 不改变 M29.5 plan、cleanup 授权、materializer visible node 创建或 asset 输出。
- 不做 hierarchy、group、layout、Auto Layout、Component、Token、Variant、Vectorization 或 quality benchmark。

## Acceptance

- report schema 为 `M29OwnershipConservationReport` / `0.1`。
- summary/meta 明确 `dslChanged=false`、`assetChanged=false`、`createdVisibleNodeCount=0`。
- `text_replay`、`image_replay`、`icon_replay`、`shape_replay` 才生成 visible replay claims。
- `preserve_in_parent_raster`、`fallback_only`、`diagnostic_only`、`suppress_duplicate` 不生成 visible claim。
- shape/text 或 shape/icon overlap 作为 background/foreground explainable overlap，不产生 blocking conflict。
- text/image overlap 只有在 M29.5 copied image asset cleanup target 和 M29.3 relation 均成立时才解释为 safe。
- report conflicts 不阻断 upload-preview；只有 report builder 编程错误才按 pipeline error 失败。

## Validation

```bash
cd backend
python3 -m py_compile app/ownership_conservation/*.py app/upload_preview/paths.py app/upload_preview/pipeline.py app/upload_preview/stages.py
uv run pytest tests/test_ownership_conservation.py -q
uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
uv run pytest -q
cd ..
pnpm -r run test
pnpm -r run typecheck
pnpm --filter @image-figma/figma-plugin run build
git diff --check
git status --short --branch
```

## Learning Backflow

Ownership conservation 是 diagnostic-only layer。后续如果要把 conflict 变成 blocking gate，必须另开计划并定义明确失败阈值，不能在本阶段悄悄改变 materialization 语义。
