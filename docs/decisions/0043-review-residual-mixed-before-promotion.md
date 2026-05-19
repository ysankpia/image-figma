# ADR: Review Residual Mixed Before Promotion

- 状态：accepted
- 日期：2026-05-19

## Context

M29.0.3.1 已经把明显文字归属的 lineage conflict 前移回 `text_noise`，同时保留 `sourceLineage` 审计信息。10 图事实显示：

```text
old mixed_symbol_text_candidate: 4063
new mixed_symbol_text_candidate: 44
text_owned_rejected_lineage: 4019
M29.0.7 bad routing: 0
visualAssets/textMembers: 504 / 741
maxWeakTextNoiseRatio: 0.0
remaining M29.1.3: future=16, keep=10, textRejected=18
```

这说明 M29.0.3.1 的方向正确：污染没有回流，mixed 桶大幅缩小。但剩余 44 个 mixed 仍然不能被当成可直接进入 visual side 的候选池。它们需要先被解释成边界问题：

```text
哪些应继续前移为 text rejection
哪些是 M29.1.3 分类规则需要调整
哪些是真正应保留的 mixed conflict
哪些只是未来可审查的 uncertain candidate
```

## Decision

新增 M29.0.3.2 Residual Mixed Boundary Review。它是 actionable audit/review，不是 routing contract。

M29.0.3.2 的 primary universe 固定为：

```text
M29.0.3 visual_evidence.json
where item.visualKind == mixed_symbol_text_candidate
```

它读取 M29.1.3、M29.0.7、M29.0.2、M29.1、M29.1.1 和 source PNG 作为 lookup/evidence reference。source PNG 只能用于 existing bbox evidence crop、review sheet 和 existing bbox audit metrics。

输出五类 review conclusion：

```text
m2903_tightening_candidate
m2913_classification_adjustment_candidate
keep_residual_mixed_conflict
candidate_for_future_uncertain_review
insufficient_evidence
```

所有 downstream permission flags 必须为 false：

```text
allowedForPromotionNow
allowedForVisualSideNow
allowedForFormalAssetNow
```

## Consequences

Benefits:

- residual mixed 不再靠直觉判断，而有可审计 review item。
- `m2903_tightening_candidate` 把下一轮是否继续前移规则变成可量化事实，不在本阶段改 M29.0.3。
- `m2913_classification_adjustment_candidate` 把分类规则问题和入口合同问题分开。
- `candidate_for_future_uncertain_review` 保留未来人工审查价值，但不打开当前 visual side。
- 80 图 full batch 可以在新 timestamped root 上复跑，失败按图记录，不覆盖旧结果。

Costs:

- 本阶段不会提升任何 residual mixed 为 formal asset。
- 本阶段增加一个 review 文档和 batch summary，但不减少剩余 mixed 本身。

Hard boundaries:

- M29.1.4 out of scope。
- M29.1.3 仍是 audit-only。
- M29.0.4/M29.0.5/M29.0.7 不消费 M29.0.3.2 输出。
- example crops 是 audit evidence，不是 `visualAssets`。
- 不新增 bbox。
- 不从 raw pixels 新切 child。
- 不重新 detector。
- 不做 promotion。
- 不生成 formal visual asset。
- 不打开 object-forming visual side。
- 不调 text overlap threshold。
- 禁止页面角色、行业特化或恢复语义合同。

M20-M28 继续是 legacy diagnostic references。OCR + M29+ 是当前正式证据链。
