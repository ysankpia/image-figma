# M29 Contract Regression Matrix

- 状态：completed
- 创建日期：2026-05-24
- 负责人：未指定

## Goal

把 M29 数学合同和数学推演文档里的关键边界转成工程回归矩阵，并补齐最高风险测试缺口，防止后续 M29 改动重新滑回局部阈值修补、错误 owner、错误 cleanup 或把 weak cluster 当组件权限。

## Scope

包含：

- 新增 `docs/engineering/m29-contract-regression-matrix.md`。
- 在 `docs/index.md` 和 `docs/engineering/testing-strategy.md` 挂矩阵入口。
- 对照现有测试标注 M29 contract case 的 `covered`、`weak`、`missing` 状态。
- 补齐本阶段发现的最高风险测试缺口。

不包含：

- 不新增 API、DSL schema、runtime stage、环境变量或存储结构。
- 不做组件化、Auto Layout、全局优化、Figma Component/Instance。
- 不重构 relation kernel 或 M29 Direct pipeline。
- 不把 M29.4 cluster 升级成 materialization 权限。

## Steps

1. 盘点现有 M29 tests，避免重复造测试。
2. 新增 M29 contract regression matrix。
3. 补齐 highest-risk weak/missing tests。
4. 更新 docs index 和 testing strategy。
5. 运行 M29 阶段验证命令。

## Acceptance

- regression matrix 至少列出 20 个 M29 合同 case。
- 每个 case 都包含 contract area、source truth、expected result、must not happen、coverage status 和 pytest target。
- M29.4 media/text weak cluster 不会被描述或测试成 `media_text_group_like` 或组件权限。
- `geometry.kind=circle/ellipse` 不能单独推出 `shape_geometry` ownership。
- 本阶段不引入可见组件化、Auto Layout、全局优化或 Figma Component/Instance 行为。

## Validation

```bash
cd backend
uv run pytest tests/test_visual_primitive_graph.py tests/test_source_ui_physical_graph.py -q
uv run pytest tests/test_region_relation_kernel.py tests/test_region_relation_graph_report.py tests/test_stable_design_cluster.py -q
uv run pytest tests/test_m29_replay_plan.py tests/test_m29_direct_replay.py -q
uv run pytest tests/test_m30_upload_pipeline.py -q
cd ..
git diff --check
git status --short --branch
```

## Notes

本阶段重点是把文档合同变成回归资产。现有测试已覆盖大量 owner、finite support、replay plan 和 cleanup 行为；新增测试只补最高风险缺口，不扩大算法范围。
