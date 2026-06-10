# 167 Slice Studio Image Only Assets And Box Color

## Summary

收窄 Slice Studio v1 的资产类型：所有手动画框资产都按 `image` 处理，删除 `icon` 作为用户可选类型。同时在 Review 工作台增加框选颜色设置，解决 UI 截图颜色和默认框颜色接近时看不清的问题。

## Scope

- `apps/slice-studio` 类型、校验、DB 初始化、Review UI、smoke、测试、README。
- 不改导出 ZIP 结构。
- 不做 AI/Pencil/Figma。

## Decisions

- v1 只支持 `image`。旧 SQLite 中已有 `icon` 记录在启动迁移时归一成 `image`。
- DB 表新建约束改为 `kind = image`。
- Review 不再显示 kind 下拉框。
- 框颜色做成 Review 本地 UI 偏好，写入 `localStorage`，不进入 manifest，也不进 SQLite。
- 颜色设置同时控制普通 slice 边框，active 仍用更醒目的 active 色；默认保持当前蓝/洋红高对比。

## Validation

- `cd apps/slice-studio && bun run check`
- `cd apps/slice-studio && bun run build`
- `cd apps/slice-studio && bun run smoke`
- 浏览器验证：没有 icon 下拉；新建/保存/export 的 kind 都是 image；颜色 input 改变后画布边框颜色改变，刷新后保留。
- `git diff --check`
