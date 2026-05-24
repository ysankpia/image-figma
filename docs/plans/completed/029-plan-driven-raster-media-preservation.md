# M29 Plan-Driven Raster/Media Preservation Mainline Cutover

- 状态：completed
- 创建日期：2026-05-24
- 完成日期：2026-05-24
- 负责人：未指定

## Goal

把当前可用的 M29 source truth 链正式收口为唯一产品主链：

```text
Upload PNG
-> OCR
-> raw M29 primitive graph
-> M29.2 source ownership
-> M29.3 region relation
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> M29 plan-driven materializer
-> /api/tasks/{taskId}/dsl
-> Renderer
-> Figma
```

本阶段迁移 raster/media preservation 能力，不迁移 M30 架构。M30 里可保留的是 asset copy、image node materialization、raster cleanup 的执行机制；M30 自己的 text editability classifier、cleanup 重算和 legacy source truth 不再保留为产品路径。

## Scope

包含：

- 新增正式 M29 plan-driven materializer。
- 让 `/api/tasks/{taskId}/dsl` 返回 M29.5 plan-driven DSL。
- 在 M29.2/M29.5 中保留可证明的 raster/media owner 和 cleanup 授权。
- 从插件 UI 移除 compare 双链路入口。
- 下线 `/api/tasks/{taskId}/m29-direct-dsl` 和 `/api/tasks/{taskId}/m30-materialization` 产品接口。
- 删除旧 M29 Direct/M30 materializer 产品路径代码、脚本和测试。
- 更新 AGENTS、README、architecture、engineering、runbook、env、bug 和 plan 文档。

不包含：

- 不做组件化、Auto Layout、Figma Component/Instance。
- 不做代码生成。
- 不做批量上传或质量看板。
- 不按黑色主题、特定截图、特定颜色、文案、语言、bbox 或行业特化。
- 不清理未跟踪的 `docs/architecture/m29-to-codia-math-contract-v0.1.md`。
- 不在本阶段继续删除 M29.0.x 离线/历史模块；它们已不是 runtime，后续若要删除需单独规划。

## Changes

- 新增 `backend/app/m29_plan_materializer.py`。
- 新增 `backend/app/m29_materialization_utils.py`，承接 M29.2/materializer 共用的中性 bbox、asset、sampling helpers。
- `backend/app/m30_upload_pipeline.py` 的历史命名 orchestrator 改为运行 M29 mainline：
  ```text
  OCR -> M29 -> M29.2 -> M29.3 -> M29.4 -> M29.5 -> M29 materialization -> M29 asset publish
  ```
- `/api/upload-m30-preview` 保留路径名，但 task stage 改为 `m29_queued` / `m29_completed`。
- `/api/tasks/{taskId}/dsl` 指向 `m29_materialized/m29_materialized_dsl.json`。
- 新增 `/api/tasks/{taskId}/m29-materialization` report endpoint。
- 删除 `/api/tasks/{taskId}/m29-direct-dsl` 与 `/api/tasks/{taskId}/m30-materialization` 当前产品接口。
- 插件只保留 `Generate from PNG` 和 `Sample`，删除 compare render path。
- M29.2 支持把大面积、复杂、image-like low-confidence raw M29 unknown 归为 `media_region` / `preserve_raster` / `image_replay`。
- M29.5 target roles 改为 `m29_text`、`m29_shape`、`m29_image`、`m29_symbol`。
- M29.5 为 visible replay actions 声明 fallback cleanup targets；copied image cleanup 仍只在 editable text contained by media 时授权。
- Materializer 从 source PNG 样本推导 root/page 背景，避免 fallback-off 时暴露固定浅色背景。

## Acceptance

- `/api/tasks/{taskId}/dsl` 是唯一正式设计稿出口，输出来自 M29 plan-driven materializer。
- 插件 UI 不再出现 compare/mainline/direct 双链路选择。
- M30 legacy materializer 不再决定正式输出。
- M29 Direct compare 产品路径不再存在。
- cleanup 权限全部可追溯到 M29.5 `cleanupTargets`。
- 深色 fallback-off 场景不暴露固定 `#F7F8FA` 白底。
- 大面积复杂 raster/media 区域可通过 M29.2/M29.5 进入 image replay。
- 简单低纹理 support 仍走 shape replay。

## Validation

已执行的 focused validation：

```text
cd backend && uv run pytest tests/test_source_ui_physical_graph.py tests/test_m29_plan_materializer.py -q
# 23 passed
```

阶段完成前还需执行：

```bash
cd backend && uv run pytest -q
cd ..
pnpm -r run test
pnpm -r run typecheck
git diff --check
git status --short --branch
```

## Notes

- `backend/app/m30_upload_pipeline.py`、`/api/upload-m30-preview` 和 `storage/m30_1_uploads/` 仍是历史命名。当前行为已经是 M29 mainline。后续若要重命名，应单独开机械迁移阶段。
- M29.0.x historical/offline modules still exist in the repository and tests, but they are not current upload runtime. Do not treat their presence as product path evidence.
