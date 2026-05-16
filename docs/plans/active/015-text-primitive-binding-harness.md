# M15 Text-Primitive Binding Harness

- 状态：active
- 创建日期：2026-05-17
- 负责人：Codex

## Summary

M15 在 M14 visible text replacement 后新增 text binding 合同层，把 OCR/replacement text 绑定到现有 visual primitives 或 M15 推断出的 UI containers，为 M16 组件化和布局重建提供输入。

M15 不改变 Figma 可见输出，不删除 fallback region，不重组图层，不改插件 UI/Main，不改 Renderer。默认生成 `/text-bindings` 报告，并只在 DSL `meta` 里记录绑定统计。

## Key Changes

- 新增 `TextPrimitiveBindingDocument v0.1`，保存到 `backend/storage/text_bindings/{taskId}.json`。
- 新增 `GET /api/tasks/{taskId}/text-bindings`。
- 新增 `text_binding_results` SQLite 表。
- 新增配置 `TEXT_BINDING_ENABLED=true`、`TEXT_BINDING_MIN_CONFIDENCE=0.70`。
- 上传链路在 M14 text replacement 后执行 M15 binding。
- 默认 fake visual primitive provider 只有 fallback regions；M15 因此会在 binding 报告中生成 `inferred_from_text_cluster` containers。
- inferred containers 只存在于 binding report，不回写 M8 visual primitives。
- DSL 只追加 `m15_text_primitive_binding` quality flag 和 `textPrimitive*` 统计，不新增可见节点。

## Binding Rules

第一版使用确定性空间规则，不接 AI：

- 短文本、hero/summary 区域、pill-like bbox 或 M14 pill strategy -> `badge` / `status_badge`。
- 顶部和 hero 区域非 badge 文本 -> `page_header` / `hero_profile`。
- summary 区域活动标题、时间和说明 -> `activity_card`。
- summary 区域同列 label/value 统计组 -> `summary_stat_card`。
- 明确 action 背景证据的居中文案 -> `primary_button`，普通 summary/stat 标题和值不能绑定为按钮。
- M14 `outline_button_text_sample` 文本 -> `outline_button` / `button_label`，优先级高于 `preview_card`。
- card grid 内标题和下方描述 -> `shortcut_card`。
- preview region 文本 cluster -> `preview_card`。
- 同一 y 线短 label 组 -> `legend_group`。
- tip region 标题和正文 -> `tip_card`。
- bottom nav 区域短 label -> `bottom_nav_item`。
- card title/subtitle/body 关系按同容器内 row 顺序和相对字号判断，不再只看单个 bbox height。
- 绑定置信度低于 `TEXT_BINDING_MIN_CONFIDENCE` 进入 `unboundTextIds`。

## Test Plan

必须通过：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

覆盖点：

- 默认上传生成 text binding report 和 DSL M15 meta。
- `TEXT_BINDING_ENABLED=false` 不生成 binding result。
- `/text-bindings` 覆盖 completed、TASK_NOT_FOUND、TEXT_BINDING_NOT_FOUND。
- 首页样例 fixture 覆盖 page header、hero profile、badge、status badge、activity card、summary stat card、primary button、outline button、shortcut card、preview card、legend group、tip card、bottom nav item。
- 回归 primary button 不吞 summary/stat 标题和值，outline button 优先于 preview card，card title/subtitle 按组内相对关系判断。
- 低于 binding confidence 的 text 进入 `unboundTextIds`。
- M15 不新增可见 DSL 节点，fallback、original_ref、hidden candidate_text、visible replacement 都保留。

## Assumptions

- M15 是关系报告，不是组件化。
- M15 默认开启，因为不改变可见输出。
- M16 才消费 binding report 做组件化、分组、图层命名和布局重建。
- M15 不处理 OCR 根本没识别到的文字。
