# M29 C-Stage Controlled Structure Materialization

- 状态：completed
- 创建日期：2026-05-25
- 负责人：Codex

## Goal

把 B 阶段的 hierarchy、sibling group、layout energy、Auto Layout permission 和 quality report 向前推进到 C 阶段：先校准高置信候选，再做 **C6-lite controlled hierarchy/group materialization**，让插件上传后的 DSL/Figma 图层结构能看到更好的 group 层级，同时保持当前视觉输出尽量不漂移。

## Scope

包含：

- C0-C2：基于 B 阶段 report 产出本阶段 materialization guardrail 和质量校准摘要。
- C6-lite：只 materialize 高置信 sibling group / hierarchy 结构为 transparent `group`，不生成真实 Auto Layout。
- 继续使用现有 DSL `group`/`frame` 能力；优先不改 DSL schema、不改 Renderer、不改 Figma plugin。
- 增加 DSL preview/diff artifact：把最终 DSL 近似渲染成 PNG，与原图做像素级 diff 指标，用于全量 15 图验证。
- `/Users/luhui/Downloads/m29` 全量 15 张 PNG batch validation。

不包含：

- 不创建 Figma Auto Layout、Component、Instance、Variant、variables 或 token binding。
- 不做 vectorization。
- 不重判 pixel owner，不改变 M29.5 replay action 或 cleanup 授权。
- 不按文件名、文案、颜色主题、行业、固定 bbox 或单张样本特化。

## Layer Diagnosis

- Source input：原始 PNG、OCR、raw M29、M29.2 source objects。
- Intermediate data：M29.3.1 relations、M29.4 clusters、M29.5 replay plan、B 阶段 reports。
- Decision point：C-stage materialization guard 只决定哪些 already-replayed visible nodes 可以被透明 group 包裹。
- Output surface：`materialized_design/design.dsl.json` 的层级结构和新增 preview/diff artifacts。
- Validation surface：backend tests、upload-preview route tests、全量 15 图 batch ledger、DSL preview/diff report。

## Steps

1. 增加 active plan 和当前文档路由。
2. 在 materializer 中增加 C-stage structure options、planner 和 report 字段。
3. 用高置信 sibling group / hierarchy evidence 对已 replayed nodes 做透明 group nesting。
4. 增加 DSL preview/diff stage，输出 preview PNG、diff PNG 和 comparison report。
5. 更新 batch validator 收集 C-stage structure 和 DSL visual comparison summary。
6. 增加 focused tests 和 upload-preview regression。
7. 跑 `/Users/luhui/Downloads/m29` 全量 15 图 batch validation，检查 artifact、stage timing 和 diff 指标。
8. 更新工程文档和 regression matrix，完成后移动到 completed。

## Acceptance

- 插件主链 `/api/upload-preview -> /api/tasks/{taskId}/dsl` 返回的 DSL 包含受控透明 group 层级，且原有 visible replay nodes 仍存在。
- `materialization_report.json` 记录 C-stage group materialization summary、accepted/rejected groups 和原因。
- 新增 DSL preview/diff artifact 可证明最终 DSL 输出和原图的视觉偏差指标。
- 15 图 batch validation 全部 completed，0 missing artifact。
- 不修改 DSL schema、不修改 Figma plugin；除非实测证明现有合同无法表达 C6-lite。
- 不出现样本特化。

## Validation

```bash
cd backend
uv run pytest tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
uv run pytest tests/test_ownership_conservation.py tests/test_hierarchy_candidate_report.py tests/test_sibling_group_candidate_report.py tests/test_layout_energy_report.py tests/test_auto_layout_permission_report.py tests/test_design_token_report.py tests/test_b_stage_quality_report.py -q
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
cd ..
pnpm -r run test
pnpm -r run typecheck
pnpm --filter @image-figma/figma-plugin run build
git diff --check
git status --short --branch
```

已执行：

```bash
cd backend
python3 -m py_compile app/plan_materializer/structure.py app/dsl_visual_comparison/pipeline.py app/dsl_visual_comparison/render.py scripts/run_upload_preview_batch_validation.py
uv run pytest tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
uv run pytest tests/test_ownership_conservation.py tests/test_hierarchy_candidate_report.py tests/test_sibling_group_candidate_report.py tests/test_layout_energy_report.py tests/test_auto_layout_permission_report.py tests/test_design_token_report.py tests/test_b_stage_quality_report.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py tests/test_source_ui_physical_graph.py -q
uv run pytest -q
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
cd ..
pnpm -r run test
pnpm -r run typecheck
pnpm --filter @image-figma/figma-plugin run build
```

验证结果：

```text
focused materializer/upload-preview: 18 passed
focused M29 regression set: 96 passed
backend full pytest: 276 passed
workspace tests: passed
workspace typecheck: passed
figma plugin build: passed
15-image batch: 15 completed, 0 failed, 0 missing artifacts
totalControlledStructureGroupCount: 169
averageDslVisualNormalizedMeanAbsError: 0.028702
maxDslVisualChangedPixelRatio10: 0.179038
```

Batch ledger:

```text
backend/tmp/validation/upload_preview_batch_20260525_053205/upload_preview_batch_validation.json
```

## Notes

- C6-lite 的核心约束是“结构可见、视觉不漂”：group 本身透明，不改变子节点 bbox、style、asset 或 replay order。
- Auto Layout permission report 只作为准入证据，不在本阶段创建 Figma Auto Layout。
