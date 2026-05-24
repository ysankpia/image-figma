# Bug: Fallback-off dark UI collapses to light background

- 状态：resolved
- 创建日期：2026-05-24
- 影响范围：M29/M29 Direct fallback-off rendering and upload preview materialization

## Summary

浅色截图在关闭 fallback 后看起来正常，但深色主题截图关闭 fallback 后会暴露大面积浅色/白色背景，复杂卡片、图表、照片或纹理区域没有被 M29 source ownership 固定为可回放 raster/media。

这不是黑色主题特例，也不是某张截图特例。根因是产品主链存在两套事实源：旧 `/dsl` 使用 legacy M30 materializer 保留了一部分 raster/media 能力，而 M29 Direct compare 路线没有把这些 raster/media preservation 能力完整纳入 M29.2/M29.5 合同；同时 base DSL 的 root/page 背景来自固定浅色默认值。

## Reproduction

1. 上传一张深色 UI PNG。
2. 使用旧 compare/direct 路线或关闭 fallback 检查输出。
3. 可见深色背景和复杂 raster/media 区域缺失，暴露固定浅色底。
4. 同样流程在浅色 PNG 上不明显，因为固定浅色默认值与源图背景接近。

## Root Cause

第一性原理上，fallback-off 结果只能由两类东西支撑：

```text
1. 已被证明可矢量回放的 shape/text/icon。
2. 已被证明必须保留的 raster/media。
```

旧实现的问题：

- M29 Direct compare 不是正式 `/dsl` 主链，M30 legacy bridge 才保留了部分 image/composite media 能力。
- M30 的 raster/media 能力和 cleanup 执行机制没有回归到 M29.2/M29.5 source ownership contract。
- root/page 背景从 deterministic base DSL 继承固定 `#F7F8FA`，深色 UI 关闭 fallback 后会直接暴露错误底色。
- copied raster/media cleanup 权限在旧 M30 中可由下游重新计算，不能被 M29.5 统一审计。

## Fix

本阶段直接切换产品主链：

```text
raw M29
-> M29.2 source ownership
-> M29.3 relation
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> M29 plan-driven materializer
-> /api/tasks/{taskId}/dsl
```

具体修复：

- 新增 M29 plan-driven materializer，并让 `/api/tasks/{taskId}/dsl` 返回其输出。
- M29.2 把大面积复杂 image-like low-confidence raw M29 unknown 归入 `media_region` / `preserve_raster` / `image_replay`。
- M29.5 为 visible replay actions 输出 final action、target role、z-order、node budget 和 cleanup targets。
- Materializer 从 source PNG 边缘样本推导 root/page background，不再暴露固定浅色默认背景。
- Materializer 只按 M29.5 `cleanupTargets` 执行 fallback erasure 和 copied image asset text cleanup。
- 删除 M29 Direct compare 产品 endpoint、legacy M30 materialization 产品 endpoint 和插件 compare UI。

## Regression Guard

后端回归：

```text
backend/tests/test_source_ui_physical_graph.py::test_large_image_like_unknown_becomes_preserved_media_region
backend/tests/test_m29_plan_materializer.py::test_m29_plan_materializer_samples_source_background_instead_of_fixed_white
backend/tests/test_m29_plan_materializer.py::test_copied_media_cleanup_requires_m295_cleanup_target
backend/tests/test_m29_plan_materializer.py::test_fallback_erasure_requires_m295_fallback_cleanup_target
backend/tests/test_m30_upload_pipeline.py::test_upload_m30_preview_samples_dark_source_background
backend/tests/test_m30_upload_pipeline.py::test_upload_m30_preview_completes_and_serves_m29_plan_driven_dsl
```

矩阵 case：

```text
M29-CR-033
M29-CR-034
M29-CR-035
M29-CR-038
M29-CR-044
M29-CR-045
```

## Validation Evidence

Focused validation:

```text
cd backend && uv run pytest tests/test_source_ui_physical_graph.py tests/test_m29_plan_materializer.py -q
# 23 passed
```

阶段完成前还需执行全量验证：

```bash
cd backend && uv run pytest -q
pnpm -r run test
pnpm -r run typecheck
git diff --check
```

## Prevention Notes

不要按“黑色主题”“深色金融图”“某个颜色”“某个文案”修。正确规则是：

```text
背景来自 source PNG 样本。
raster/media preservation 来自 source evidence + M29.2 owner。
visible nodes 来自 M29.5 plan。
cleanup 来自 M29.5 cleanupTargets。
```

如果未来再次出现 fallback-off 坍塌，先查 M29.2 owner 和 M29.5 plan，不要在 Renderer 或 plugin 里补样式。
