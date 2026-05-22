# ADR: Gate Unit Candidates Before Promotion And Componentization

- 状态：accepted
- 日期：2026-05-22

## Context

M30/M37/M38/M39 已经把项目推进到可编辑图层和少量安全分组阶段。M39.1 进一步报告了 product-card、banner、chrome-shell、content-section 等候选。

但当前 M39.1 候选仍包含明显碎片，例如小 icon、小图片、重复 bbox、micro unit 和模型孤证。此时如果直接进入 M39.2 promotion、M40 nested hierarchy 或 M41 Component/Instance，会把错误候选固化成错误结构。

Codia 公开路线显示其核心不是直接生成 Figma Component，而是先形成类似 `VisualElement` 的统一 DSL，再逐步包含 `childElements`、`layoutConfig` 和可选 `componentSpec`。这说明本项目也应先保证 unit truth，再谈 layout 和 component。

Figma MCP 可以把已有 Figma 图层树转成 HTML/CSS，但它读取的是已经结构化的 Figma 节点，不是原始 PNG。它不能替代当前 `PNG -> evidence -> DSL -> Figma` 主链路。

## Decision

将后续阶段顺序固定为：

```text
M39.1.1 Unit Candidate Quality Gate
-> M39.2 Unit Promotion
-> M40 Layout Semantics
-> M41 Component / Instance Extraction
```

M39.1.1 必须先把 candidate unit 分出 `promotionReady`、`qualityTier`、`qualityReasons`、`rejectReasons` 和重复关系。只有通过质量门的候选才能进入 M39.2。

M40 不再作为当前下一阶段。M40 必须等待 M39.2 产生稳定 promoted units 后再启动。

M41 Component/Instance 必须等待 unit 和 layout 语义稳定后再启动。组件化不能用来修复错误 unit，只能消费已经可信的 unit。

模型、UIC、Codia schema、Figma MCP 输出都只能作为候选或参考，不允许绕过 M39.1.1/M39.2 的证据门禁。

## Consequences

好处：

- 避免把 icon fragment、micro unit 和模型孤证提升成错误结构。
- 把“是否组件化”的问题推迟到 unit/layout 已可信之后。
- 后续代理有明确阶段顺序，不会因为局部 UI 问题跳到单点 hack 或提前 M40/M41。

代价：

- 短期内不会显著增加 Figma Component/Instance 数量。
- 需要先接受“少 promotion、少错误”的保守策略。
- M40 既有计划被延后，需要按新路线重写为 layout semantics，而不是立即实现 nested hierarchy。

后续影响：

- `docs/roadmap.md` 成为阶段顺序事实来源。
- M39.1.1 是下一阶段。
- M39.2 之后再重新评估 M40/M41 的实现范围。
