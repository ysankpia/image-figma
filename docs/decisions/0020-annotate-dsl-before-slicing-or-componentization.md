# ADR 0020: Annotate DSL Before Slicing Or Componentization

- 状态：accepted
- 日期：2026-05-17

## Context

M16 已经能把 M15 text bindings 聚合为 component candidates 和 layout groups，但这些结构仍然只存在于旁路 JSON。Figma layer tree 仍主要由 fallback、hidden candidate text、replacement cover 和 visible text 组成，缺少稳定的 component/group 归属索引。

如果直接进入切图、局部 fallback 删除、真实 group 或组件化，失败会影响可见输出，并且很难判断哪个 DSL layer 属于哪个 component。

## Decision

M17 先做 DSL component annotation 和 layer naming：

- 新增 `ComponentAnnotationDocument v0.1`。
- 新增 `/api/tasks/{taskId}/component-annotations`。
- 通过 M16 component -> M15 binding -> OCR block id -> DSL element id 做确定性 join。
- 只修改已有 DSL element 的 `name` 和 `meta`。
- 不切图、不创建 Figma group/component、不删除 fallback、不改变可见输出。

## Consequences

M18+ 可以基于 M17 annotation 判断哪些 text、cover、fallback context 和未来 asset slices 属于同一个 component/group。这样后续切图、局部 fallback 替换和组件化可以从可追踪索引开始，而不是直接对图片做危险操作。
