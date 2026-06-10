# 166 Slice Studio Page Rail Drag Reorder

## Summary

把 Review 左侧 page rail 的页面顺序操作从四个按钮改为拖拽排序。左侧只承担页面选择和排序；右侧 inspector 继续承担页面命名、替换、删除。删除重复语义，避免同一动作在左右两处出现。

## Scope

- 修改 `apps/slice-studio/components/review/ReviewWorkbenchClient.tsx`。
- 修改 `apps/slice-studio/app/globals.css`。
- 不改 API、SQLite、导出合同。
- 不接 AI/Pencil/Figma。

## Behavior

- 左侧 page rail 每页显示一个横条拖拽 handle。
- 按住 handle 上下拖动，可调整页面顺序。
- 拖拽排序保存到后端，刷新后顺序不丢。
- 左侧不再显示上移、下移、替换、删除四个按钮。
- 右侧 inspector 不再显示上移/下移，只保留替换、删除。
- Undo 仍可撤销页面排序。

## Validation

- `cd apps/slice-studio && bun run check`
- `cd apps/slice-studio && bun run build`
- `cd apps/slice-studio && bun run smoke`
- 浏览器验证左侧拖拽排序、刷新后顺序保持、右侧只显示替换/删除。
- `git diff --check`
