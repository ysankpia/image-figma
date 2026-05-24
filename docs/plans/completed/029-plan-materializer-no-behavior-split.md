# M29 Plan Materializer No-Behavior Split

- 状态：completed
- 创建日期：2026-05-24
- 完成日期：2026-05-24
- 负责人：未指定

## Goal

把单文件 plan materializer 拆成职责清楚的 package，降低后续修改 M29 materialization 时误碰 owner、cleanup 或 replay 合同的概率。

本阶段是无行为变化拆分：不改 API、不改 DSL、不改 report schema、不改 storage path、不改 Renderer、不改插件 UI、不新增 fallback 或主题特化规则。

## Scope

包含：

- 新增 `backend/app/plan_materializer/` package。
- 对外入口改为 `build_plan_driven_dsl`。
- 对外类型改为 `PlanMaterializerOptions`、`PlanMaterializerResult`。
- 删除旧 `backend/app/m29_plan_materializer.py`。
- 更新 upload preview pipeline 和 materializer tests 的 import。
- 更新当前 code map / backend architecture / roadmap 文档。

不包含：

- 不改变 M29.5 replay plan consumption。
- 不重新判断 owner。
- 不改变 cleanup 授权。
- 不改变 `M29PlanMaterializationReport` schema。
- 不改变 DSL roles：`m29_text`、`m29_shape`、`m29_image`、`m29_symbol`。

## Module Boundary

```text
backend/app/plan_materializer/__init__.py
backend/app/plan_materializer/builder.py
backend/app/plan_materializer/types.py
backend/app/plan_materializer/background.py
backend/app/plan_materializer/replay.py
backend/app/plan_materializer/assets.py
backend/app/plan_materializer/cleanup.py
backend/app/plan_materializer/report.py
```

Responsibilities:

```text
builder.py: entry flow, base DSL setup, output file writes
background.py: source/text background sampling, foreground sampling, source-derived shape style
replay.py: M29.5 plan item to DSL node conversion
assets.py: crop/copy image assets and local asset URL helpers
cleanup.py: execute only M29.5-authorized fallback/copied image cleanup
report.py: summary/report helper
types.py: dataclasses for options/result/replay nodes
```

## Acceptance

- `backend/app/plan_materializer/*.py` files are each below roughly 350 lines.
- `backend/app/m29_plan_materializer.py` is removed.
- `/api/upload-preview -> /api/tasks/{taskId}/dsl` behavior remains unchanged.
- Materializer tests keep passing.
- No production import of `app.m29_plan_materializer` remains.

## Validation

阶段回归命令：

```bash
cd backend
uv run pytest tests/test_m29_plan_materializer.py -q
uv run pytest \
  tests/test_upload_preview_pipeline.py \
  tests/test_m29_replay_plan.py \
  tests/test_source_ui_physical_graph.py \
  tests/test_region_relation_kernel.py \
  tests/test_region_relation_graph_report.py \
  tests/test_stable_design_cluster.py \
  -q
uv run pytest -q
cd ..
pnpm -r run test
pnpm -r run typecheck
pnpm --filter @image-figma/figma-plugin run build
git diff --check
```

静态检查：

```bash
wc -l backend/app/plan_materializer/*.py
rg -n "from app\\.m29_plan_materializer|import app\\.m29_plan_materializer|m30_upload_pipeline|upload-m30-preview" backend/app backend/tests figma-plugin/src
```
