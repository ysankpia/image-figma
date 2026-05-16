# M16 Component Structure Harness

- 状态：active
- 创建日期：2026-05-17
- 负责人：Codex

## Summary

M16 在 M15 `text-bindings` 之后新增 component structure 合同层，把 M15 的 containers 和 bindings 聚合成可验证的 UI component candidates 与 layout groups。它给 M17+ 的图层命名、分组实验、局部 fallback 替换和正式组件化提供结构输入。

M16 默认不改变 Figma 可见输出，不新增可见 DSL 节点，不创建 Figma Component/Instance，不删除 fallback region，不改 Renderer，不改插件 UI/Main。当前阶段只生成 `/component-structures` 报告，并在 DSL `meta` 里追加结构统计。

## Key Changes

- 新增 `ComponentStructureDocument v0.1`。
- 新增持久化目录 `backend/storage/component_structures/{taskId}.json`。
- 新增只读接口 `GET /api/tasks/{taskId}/component-structures`。
- 新增 SQLite 表 `component_structure_results`。
- 新增配置 `COMPONENT_STRUCTURE_ENABLED=true` 和 `COMPONENT_STRUCTURE_MIN_CONFIDENCE=0.70`。
- 上传链路在 M15 text binding 后执行 M16 component structure。
- DSL 只追加 `m16_component_structure_harness` quality flag 和 `componentStructure*` 统计。

## Document Contract

`ComponentStructureDocument v0.1` 包含：

- `components`：由 M15 containers/bindings 聚合出的 component candidates。
- `groups`：由 component alignment 和布局模式推断出的 layout groups。
- `unstructuredContainerIds`：低置信度、未知角色或无法安全聚合的 M15 container。
- `meta`：component/group/unstructured 计数、role summary、group role summary、layout summary。

第一版 component role：

```text
page_header
hero_profile
badge
status_badge
activity_card
summary_stat_card
primary_button
outline_button
shortcut_card
preview_card
legend_group
tip_card
bottom_nav
bottom_nav_item
unknown
```

第一版 group role：

```text
summary_stat_group
shortcut_grid
preview_section
bottom_nav_group
page_structure
```

第一版 layout pattern：

```text
single
vertical_stack
horizontal_row
three_column_row
grid_2x2
bottom_nav_row
unknown
```

## Pipeline

M16 后上传链路：

```text
POST /api/upload
-> deterministic fallback DSL
-> visual primitives
-> OCR
-> hidden candidate patch
-> visible text replacement
-> text binding
-> component structure
-> save final DSL
-> task completed
```

M16 输入：

- `OCRDocument`
- `VisualPrimitiveDocument`
- `TextReplacementDocument`
- `TextPrimitiveBindingDocument`
- 当前 DSL
- image size

M16 输出：

- `backend/storage/component_structures/{taskId}.json`
- `component_structure_results` row
- DSL meta M16 标记和统计

## Inference Rules

M16 不按中文文案、不按单张图绝对坐标、不接 AI。它只消费 M15 已有事实：

- `binding.containerRole`
- `binding.relationship`
- `binding.bbox`
- `binding.containerBBox`
- `binding.confidence`
- `container.role`
- `container.source`
- `container.bbox`
- `container.confidence`

组件生成规则：

- `page_header` container -> `page_header` component。
- `hero_profile` container 可关联附近 `badge` children -> `hero_profile` component。
- `activity_card` container 可关联附近 `status_badge` -> `activity_card` component。
- `summary_stat_card` containers -> `summary_stat_card` components。
- `primary_button` / `outline_button` containers -> button components。
- `shortcut_card` containers -> `shortcut_card` components。
- `preview_card` 可关联 `outline_button` 和 `legend_group` -> `preview_card` component。
- `tip_card` container -> `tip_card` component。
- `bottom_nav_item` containers -> `bottom_nav_item` components。

分组规则：

- 2 个以上同 row 的 `summary_stat_card` -> `summary_stat_group`。
- 4 个 `shortcut_card` 按 2x2 排列 -> `shortcut_grid`。
- `preview_card` 内含 outline button 或 legend group -> `preview_section`。
- 2 个以上同 row 的 `bottom_nav_item` -> `bottom_nav_group`。
- 页面主要 component 按 y 顺序 -> `page_structure`。

fallback region 只作为上下文，不生成高置信业务 component。

## Failure Strategy

- `COMPONENT_STRUCTURE_ENABLED=false` 时不生成 result，不追加 DSL M16 meta。
- M16 failed/skipped 不影响 upload completed。
- validation failed 保存 failed document，写 `error_logs`，`/dsl` 回退 M15 输出。
- `GET /component-structures` 对 task missing、result missing、file missing 返回稳定错误码。

## Test Plan

必须通过：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

覆盖点：

- 默认上传生成 component structure report 和 DSL M16 meta。
- `COMPONENT_STRUCTURE_ENABLED=false` 不生成 report，DSL 保持 M15 输出。
- `/component-structures` 覆盖 completed、TASK_NOT_FOUND、COMPONENT_STRUCTURE_NOT_FOUND。
- M16 failed/skipped 不影响 upload completed。
- validation failed 保存 failed document，DSL 回退 M15 输出。
- page header、hero profile、activity card、summary stat、primary/outline button、shortcut grid、preview section、tip card、bottom nav group、page structure 规则。
- fallback region 不生成高置信业务 component。
- 低于 `COMPONENT_STRUCTURE_MIN_CONFIDENCE` 的 container 进入 `unstructuredContainerIds`。
- M16 不新增可见 DSL 节点，fallback、original_ref、hidden candidate_text、visible replacement 都保留。

## Assumptions

- M16 是 component structure report，不是正式组件化。
- M16 默认开启，因为不改变 Figma 可见输出。
- M16 不删除 fallback region。
- M16 不创建 Figma Component/Instance。
- M16 不改插件 UI/Main，不改 Renderer。
- M16 不接新 OCR/AI provider。
- M16 不把 inferred component 写回 visual primitives。
- M17 再考虑 DSL annotation、图层命名和 grouping experiment。
- M18 以后再考虑局部 fallback 删除、正式组件化和 Auto Layout。
