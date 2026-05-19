# M13 Text Replacement Quality Control

- 状态：active
- 创建日期：2026-05-17
- 负责人：Codex

## Summary

M13 在 M12 text replacement 后增加质量控制和 apply 回退。它不扩大 OCR，不放宽 `complex_background`，不重建图标、头像、卡片、组件或 Auto Layout。

M13 的目标是让每个 replacement decision 都可解释：OCR 是否识别到、基础 replacement 是否 accepted、质量门禁是否允许 apply、如果被阻断原因是什么。

## Key Changes

- 继续使用 `TextReplacementDocument v0.1` 和 `GET /api/tasks/{taskId}/text-replacements`。
- 每个 decision 增加 `quality` 和 `application` 字段。
- `TEXT_REPLACEMENT_MODE=apply` 只阻断 high-risk accepted replacement；medium-risk replacement 记录 caution 但仍可应用。
- `meta` 增加 applied/blocked/risk/region/reason 统计。
- DSL meta 增加 `m13_text_replacement_quality_control`、`textReplacementAppliedCount` 和 `textReplacementBlockedCount`。

## Test Plan

必须通过：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

覆盖点：

- debug 模式生成 quality/application 但不改 DSL。
- apply 模式只阻断 high-risk replacement。
- medium-risk decision 保留报告但仍可进入 DSL，避免粗略 region caution 造成大面积回退。
- rejected decision 标记 high risk 和 `decision_not_accepted`。
- 首页样例相关文字能被报告为 OCR 已识别但 replacement 拒绝。

## Assumptions

- M13 不修复所有文字覆盖率问题，正式放开 badge/button/card/tip/legend 文本替换进入 M14。
- 不新增 API、数据库表、Renderer 能力或插件协议。
