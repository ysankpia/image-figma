# 164 Slice Studio Page Naming And Asset List Density

## Summary

修复 Review 右侧 inspector 的两个实际可用性问题：

- asset row 内容溢出，bbox 信息默认占空间，导致列表无法稳定阅读。
- page 只有 `P1/P2` 顺序号和原文件名，缺少用户可编辑的业务页面名，导出时也无法形成 `P1-首页` 这类稳定目录。

本轮继续保持主线简单：不改切图坐标合同，不引入多选，不接 AI，不改 assets.zip 总体结构，只给 page 增加可编辑显示名并优化右侧列表密度。

## Contract

- `pages.display_name` 是用户可编辑业务名，默认空。
- 页面顺序仍由 `page_index` 决定，显示为 `P1`、`P2`。
- UI 展示格式为：`P1` + `displayName || originalName`。
- 导出路径使用 `P1-{displayNameSlug}`，如果没有 display name，则仍为 `P1`。
- `manifest.json` 增加 `displayName` 和 `pageDirectory`。
- `project.json` 继续包含 pages，新增字段随 API 返回。

## Scope

- 新增 `PATCH /api/projects/:projectId/pages/:pageId`，请求体 `{ "displayName": "首页" }`。
- SQLite `pages` 表新增 `display_name TEXT NOT NULL DEFAULT ''`。
- 老库启动时自动补列。
- Review 左侧 page rail 和右侧 summary 支持重命名当前页。
- Asset list 默认只显示编号、名称、类型、删除；bbox 只在 active asset panel 展示。
- Asset row 修复溢出，不再把 bbox 文本、select、删除按钮挤出容器。

## Validation

- `cd apps/slice-studio && bun run check`
- `cd apps/slice-studio && bun run build`
- `cd apps/slice-studio && bun run smoke`
- Chrome DevTools MCP 验证 Review 页面：
  - asset row 不溢出。
  - inactive rows 不显示 bbox。
  - 点击 row 后 active panel 显示 bbox。
  - 当前 page 可重命名。
  - 刷新后页面名保留。
  - console 无 error/warn。
- `git diff --check`

## Completion Evidence

- `cd apps/slice-studio && bun run check` passed.
- `cd apps/slice-studio && bun run build` passed.
- `cd apps/slice-studio && bun run smoke` passed, including ZIP entries `originals/P1-首页.png` and `slices/P1-首页/slice_0001.png`.
- Chrome DevTools MCP checked current Review page:
  - 10 asset rows, `overflowCount=0`.
  - inactive rows show only `#`, name, kind, delete.
  - clicking a row shows active bbox x/y/w/h in the active asset panel.
  - `PATCH /api/projects/:projectId/pages/:pageId` returned 200 for page rename.
  - console had no error/warn messages.
