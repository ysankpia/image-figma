# 170 Slice Studio Inspector Scroll And Favicon

## Summary

修 Review 右侧 Inspector 资产多时不好滚动的问题，并顺手清掉 Next dev 下 `/favicon.ico` 404。

当前问题：

- 右侧 Inspector 内容越来越多，资产列表只能看到一小段。
- 如果把整个右侧做滚动，页面信息、裁切模式、框颜色会一起滚走，不适合生产流。
- DevTools Console 有 `/favicon.ico` 404，干扰验收。

## Scope

- 只改 `apps/slice-studio` Review 右侧布局和 favicon route。
- 不改 API、SQLite、导出、裁切算法。
- 不新增 UI 组件库。

## Behavior

- 右侧 Inspector 分为：
  - 固定控制区：标题、裁切模式、页面信息、框颜色、active asset。
  - 独立滚动区：资产列表。
- 资产列表滚动条默认隐藏，但仍可滚动。
- 上方控制区做垂直压缩，减少占用。
- `/favicon.ico` 返回一个最小图标，不再 404。

## Validation

- `cd apps/slice-studio && bun run check`
- `cd apps/slice-studio && bun run build`
- Chrome DevTools 验收：
  - 多资产时资产列表可独立滚动到底。
  - 上方裁切模式/页面信息不随资产列表滚走。
  - Console 无业务 error；`favicon.ico` 不再 404。
