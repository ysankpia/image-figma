# ADR 0018: Bind Text To Visual Primitives Before Components

- 状态：accepted
- 日期：2026-05-17

## Context

M14 已经能把大量 OCR text 变成 visible replacement，但这些 text 仍然只是覆盖在 fallback 图上的独立图层。系统不知道哪些文字属于按钮、badge、卡片、图例或底部导航。

默认 `VISUAL_PRIMITIVE_PROVIDER=fake` 只提供 header/content/bottom 三个 fallback region primitive。如果 M15 只绑定到现有 primitives，结果只能得到大区域归属，不能支撑 M16 组件化。

## Decision

新增 M15 text-primitive binding harness：

- 生成独立 `TextPrimitiveBindingDocument v0.1`。
- 新增 `/api/tasks/{taskId}/text-bindings`。
- 允许 binding report 包含 `inferred_from_text_cluster` UI containers。
- inferred containers 不回写 visual primitives。
- DSL 只追加 binding meta，不改变可见输出。

## Consequences

M16 可以消费 binding report 做组件化和布局重建，而不污染 M8 visual primitive 合同。M15 的输出可回归、可解释、低风险。

M15 不解决图标重建、Auto Layout、fallback 删除或真实组件实例化。这些进入 M16 以后。
