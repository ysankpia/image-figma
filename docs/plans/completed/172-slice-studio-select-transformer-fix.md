# 172 Slice Studio Select Transformer Fix

- 状态：completed
- 创建日期：2026-06-11
- 负责人：Codex

## Goal

修复 Review 画布中画框后切到选择模式无法拖动、无法拉边、无法拉角缩放的问题。

## Scope

包含：

- `apps/slice-studio/components/review/ReviewWorkbenchClient.tsx` 的 Konva Rect / Transformer 绑定和事件命中。
- 必要的前端检查与浏览器验收。

不包含：

- 导出算法、SQLite、API、AI/OCR、Pencil/Figma。
- 新 UI 结构重构。

## Current Problem

当前 `Transformer` 渲染依赖 `activeRectRef.current`，但 ref 变化不会触发 React 重新渲染，导致选中 slice 后缩放器可能没有挂载。点击 Transformer handle 时，事件还会冒泡到 Stage，Stage 因为没有读到 `sliceId` 而清空 active slice，handle 一按就消失。

## Steps

1. 用 slice id 到 Konva Rect node 的 ref map 替代单个 active ref。
2. `Transformer` 在选择模式且存在 active slice 时始终渲染。
3. effect 中按 `activeSliceId` 从 ref map 查找 node 并绑定 Transformer。
4. Stage select 事件忽略 Transformer 和 anchor 节点。
5. Rect drag start 时确保当前 slice 被设为 active。

## Acceptance

- 画框后切到选择模式，可点击 slice 选中。
- active slice 显示 8 个 handle。
- 拖动 slice 可移动。
- 拖动边和角可缩放。
- 拖动 handle 不会让 active slice 丢失。

## Validation

- `cd apps/slice-studio && bun run typecheck`
- `cd apps/slice-studio && bun run test`
- 浏览器打开 Review 页面手动验证 select/drag/resize。
- `git diff --check`
