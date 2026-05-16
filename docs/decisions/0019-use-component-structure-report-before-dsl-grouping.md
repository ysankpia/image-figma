# ADR 0019: Use Component Structure Report Before DSL Grouping

- 状态：accepted
- 日期：2026-05-17

## Context

M15 已经把 OCR/replacement text 绑定到 visual primitives 或 inferred UI containers。下一步如果直接改 DSL 图层、创建 group、删除 fallback 或生成 Figma component，会把还不稳定的推断结果推到可见输出里，失败代价太高。

当前 fake visual primitive provider 仍主要提供 fallback region。真正有价值的结构信息来自 M15 binding report，而不是 Figma 图层树本身。因此 M16 应先把 binding 聚合成可验证的 component candidates 和 layout groups，作为后续阶段输入。

## Decision

新增 M16 component structure harness：

- 生成独立 `ComponentStructureDocument v0.1`。
- 新增 `/api/tasks/{taskId}/component-structures`。
- 新增 `component_structure_results` 索引表。
- 默认开启 `COMPONENT_STRUCTURE_ENABLED=true`，因为它不改变 Figma 可见输出。
- 只消费 M15 binding facts，不按单张图文案或绝对坐标写特化逻辑。
- DSL 只追加 M16 meta，不新增可见节点。

## Consequences

M17 可以基于 component structure report 做 DSL annotation、图层命名和分组实验，而不把 M16 的推断误差直接暴露到 Figma 可见结果。

M16 不解决正式组件化、Auto Layout、fallback 删除、图标重建或局部结构化替换。这些必须在后续阶段基于 M16 报告继续收敛。
