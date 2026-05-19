# ADR: Classify Mixed Symbol/Text Conflicts Before Promotion

- 状态：accepted
- 日期：2026-05-19

## Context

M29.1.1/M29.1.2 保留了 OCR 前的 symbol lineage。10 张 lineage-aware batch comparison 证明主链路没有被污染：

```text
bad mixed routing: 0
visualAssets: 504 -> 504
textMembers: 741 -> 741
weakTextNoiseUnresolvedRatio max: 0.0
```

但 `mixed_symbol_text_candidate` 达到 4063 个，平均占 visual evidence 的 0.838089，最高 0.900915。这个桶不是图标候选池，而是 OCR/Text ownership 与 pre-OCR visual lineage 的冲突桶。里面同时包含真实小视觉元素、文字笔画、数字、标点、边框和弱碎片。

## Decision

新增 M29.1.3 Mixed Symbol/Text Conflict Classification Audit。它只分类 M29.0.3 `mixed_symbol_text_candidate`，输出三类：

```text
future_promotable_uncertain_symbol_candidate
keep_mixed_symbol_text_conflict
text_owned_rejected_lineage
```

M29.1.3 是 audit contract，不是 routing contract。所有 conflict 的 downstream permission flags 必须为 false：

```text
allowedForCurrentPromotion
allowedForObjectFormingVisualSide
allowedForFormalVisualAsset
allowedForRoutingChange
```

M29.1.3 不修改 M29.0.3/M29.0.7/M29.0.4/M29.0.5，不生成 formal visual asset，不恢复图标，不让 mixed 进入 object-forming visual side。任何 promotion 必须等 M29.1.4，并且第一版也只能 controlled uncertain promotion。

## Consequences

好处：

- mixed 冲突桶变成可审计、可回归的分类结果。
- `text_owned_rejected_lineage` 成为一等反证分类，防止文字碎片回流 visual asset。
- 后续 M29.1.4 是否值得做，可以基于分类分布和 examples 判断。

代价：

- 当前阶段不会恢复图标，也不会增加 formal visual asset。
- mixed 比例高的问题不会被隐藏，而会显式暴露为分类审计工作。

硬边界：

- example crops 只是 audit evidence，不是 visual assets。
- 禁止新增页面角色或行业特化合同。
- 禁止新增 `recoverable_icon`、`promotable_icon`、`icon_recovery`、`restore` 等恢复语义。
