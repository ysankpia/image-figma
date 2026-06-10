# 163 Slice Studio Review Editor Density

## Summary

优化 `apps/slice-studio` 的 Review 编辑器页。目标是把已经可用的切图闭环整理成更像生产工具的界面：顶部状态更短，悬浮工具栏只保留工具，右侧 inspector 更紧凑。

本轮不改 API、SQLite、导出结构、bbox 坐标规则、保存逻辑和 Konva 画布交互。

## Scope

- 移除悬浮工具栏里的删除按钮。删除是动作，不是工具状态。
- 顶部栏压缩缩放和保存状态展示，避免长状态文本常驻占空间。
- 右侧 `selected` 文案改为事实语义 `assets`，因为当前没有多选模型。
- active asset 编辑区改成紧凑 header + 行内字段 + 小删除按钮。
- asset list 改成紧凑行，保留改名、改 kind、删除、选中能力。
- 仅在空页面或空 assets 时显示操作引导；已有 assets 时不常驻占位文案。

## Validation

- `cd apps/slice-studio && bun run check` passed.
- `cd apps/slice-studio && bun run build` passed.
- `git diff --check` passed.
- Chrome DevTools MCP opened `http://127.0.0.1:3010/projects/project_mq8gypro_19995c99/review`.
- Browser DOM verification passed:
  - floating toolbar has 3 buttons: select, draw, pan.
  - inspector header uses `assets`, not fake `selected` wording.
  - topbar does not show the long restored-project status.
  - active asset panel opens after selecting an asset row.
  - delete is represented by compact icon actions, not a toolbar mode.
  - current console has no error/warn/issue messages.
- Screenshot was captured during browser validation, then removed from the worktree as temporary evidence.
