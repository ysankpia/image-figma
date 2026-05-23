# M29.5 Replay Engine V2: Quality Replay Plan

- 状态：active
- 创建日期：2026-05-23
- 负责人：未指定

## Goal

把 M29.2 source ownership、M29.3.1 relation graph 和 M29.4 stable clusters 收束成一个只读的 replay 决策层，再由 `m29_direct_replay` 按计划生成左侧 DSL。

目标不是更聪明的语义理解，而是更少的重影、错回放、漏回放和节点爆炸。

## Scope

包含：

- 新增 `m29_5_replay_plan` 只读阶段。
- 生成 `storage/m30_1_uploads/{taskId}/m29_5/replay_plan.json`。
- 让 `m29_direct_replay` 优先消费 replay plan。
- 允许 M29.5 降级失败后回退到当前 M29.2 direct replay 行为。
- 将 M29.4 cluster 作为弱结构证据注入 replay 决策，但不做组件化、不做语义 detector。

不包含：

- 不改主线 `/api/tasks/{taskId}/dsl`。
- 不改插件 compare UI。
- 不做 Auto Layout。
- 不做 Component/Instance。
- 不把 M29.5 变成新的 UI 语义 detector。

## Acceptance

- M29.5 输出只读 replay plan，不创建可见节点，不改 asset。
- `m29_direct_replay` 仅在 plan 存在时优先按 plan 决策生成 visible nodes。
- `preserve_in_parent_raster` 不生成 editable text，不擦 copied image，不擦 fallback。
- `near_equal` 重复 evidence 只保留一个 replay owner。
- editable text contained by media 时，plan 必须声明 fallback 和 copied image asset cleanup target。
- 节点预算由 plan 裁决，不能让 replay 阶段再炸层。

## Validation

```bash
cd backend
uv run pytest tests/test_m29_replay_plan.py -q
uv run pytest tests/test_m29_direct_replay.py tests/test_region_relation_kernel.py -q
uv run pytest tests/test_m30_upload_pipeline.py tests/test_routes_tasks.py -q
cd ..
git diff --check
git status --short --branch
```

## Notes

- M29.5 的 replay plan 是 compare 左侧实验路径的质量门，不是默认路径切换。
- 若 M29.3.1 或 M29.4 缺失，M29.5 允许降级生成 plan。
- 若 M29.5 自身失败，`m29_direct_replay` 回退到当前 M29.2 direct replay 行为。
