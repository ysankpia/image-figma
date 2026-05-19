# ADR: Reject Text-Like Lineage Before Mixed Conflict

- 状态：accepted
- 日期：2026-05-19

## Context

M29.1.1/M29.1.2 修复了一个真实的信息丢失点：有 OCR 前视觉血统的候选，不应被 high OCR overlap 直接压成 plain `text_noise`。因此 M29.0.3 lineage-aware path 引入了：

```text
high OCR overlap + surviving pre-OCR lineage
=> mixed_symbol_text_candidate
```

M29.1.3 进一步证明这个 bucket 的性质：它是冲突桶，不是图标候选池。当前 batch 分类结果是：

```text
mixedCount: 4063
textRejectedCount: 4029
futurePromotableCount: 24
keepMixedCount: 10
badRoutingCountFromM2907: 0
visualAssetCountFromM2905: 504
maxWeakTextNoiseRatioFromM2906: 0.0
```

主链路没有污染，但 mixed 入口太宽。继续让 4029 个强文字反证候选进入 mixed，只会把后续审计噪声推到 M29.1.3，而不是解决信息合同。

## Decision

在 M29.0.3 增加 M29.0.3.1 Text-Rejected Lineage Feedback Gate。它只影响传入 M29.1 lineage JSON 的 path；未传 lineage JSON 时，baseline M29.0.3 完全不变。

新合同：

```text
high OCR overlap + no surviving lineage
=> text_noise

high OCR overlap + surviving lineage + strong text counter-evidence
=> text_noise
=> decision=noise
=> sourceLineage.rejectedLineageReason=text_owned_rejected_lineage
=> sourceLineage.conflictClass=text_owned_rejected_lineage
=> sourceLineage.survivingPreOcrSymbolCandidate=false

high OCR overlap + surviving lineage + no strong text counter-evidence
=> mixed_symbol_text_candidate
=> decision=uncertain
```

M29.0.7 keeps routing conservative. Rejected-lineage `text_noise` remains text-owned when OCR overlap/confidence supports it, visual side remains disallowed, and `sourceLineage` is copied into the ownership decision for audit.

M29.1.3 remains audit-only and only classifies remaining `mixed_symbol_text_candidate` items. It is not a downstream routing source.

## Consequences

Benefits:

- The mixed bucket should shrink at the source instead of being cleaned downstream.
- `text_owned_rejected_lineage` becomes a stable audit reason in M29.0.3 and M29.0.7.
- M29.1.3 can focus on the remaining ambiguous mixed conflicts.
- `preOcrSymbolCandidate` remains a historical provenance fact; `survivingPreOcrSymbolCandidate=false` records why it no longer survives as visual/mixed conflict evidence.

Costs:

- `text_noise` will reasonably rise in lineage-aware batches.
- M29.0.3 now reads M29.0.2 text boxes for lineage-aware counter-evidence, but does not call OCR or detect new bboxes.

Boundaries:

- No promotion.
- No formal visual asset.
- No object-forming visual side for rejected lineage.
- No M29.1.4 in this stage.
- No page or industry-specific contracts.
- M20-M28 are legacy experiments / diagnostic references for current reconstruction decisions; OCR + M29+ is the active evidence chain.
