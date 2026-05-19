# M29.0.3.1 Text-Rejected Lineage Feedback Gate

- 状态：completed
- 创建日期：2026-05-19
- 完成日期：2026-05-19
- 负责人：Codex

## Goal

M29.0.3.1 收紧 lineage-aware M29.0.3 的入口合同，把 M29.1.3 已经证明有效的文字反证前移到 M29.0.3。目标不是恢复图标、promotion 或打开 visual side，而是让明显文字归属的 lineage conflict 不再进入 `mixed_symbol_text_candidate` 大桶。

第一性原理判断：

```text
source fact: OCR/textBoxes 是文字归属的独立证据。
source fact: M29/M29.1 sourceLineage 只是 OCR 前视觉血统，不是资产许可。
failure point: M29.0.3 把 high OCR overlap + surviving lineage 全部放进 mixed 桶。
evidence: M29.1.3 把 4063 个 mixed 进一步分类，其中 4029 个是 text_owned_rejected_lineage。
correct object: M29.0.3 lineage-aware classification gate，而不是 M29.0.7 或 M29.1.3 routing。
```

当前 M29.1.3 batch 事实：

```text
mixedCount: 4063
textRejectedCount: 4029
futurePromotableCount: 24
keepMixedCount: 10
badRoutingCountFromM2907: 0
visualAssetCountFromM2905: 504
maxWeakTextNoiseRatioFromM2906: 0.0
```

这些数据说明：主链路没有污染，但 M29.0.3 的 lineage-aware mixed 入口太宽。正确修法是让强文字反证先回到 `text_noise`，同时保留 `sourceLineage` 审计字段。

## Scope

M29.0.3.1 只改变传入 `--m291-lineage-json` 的 lineage-aware path：

```text
未传 --m291-lineage-json
=> M29.0.3 baseline 完全不变

high OCR overlap + no surviving lineage
=> text_noise

high OCR overlap + surviving lineage + strong text counter-evidence
=> text_noise
=> decision=noise
=> reasons += text_owned_rejected_lineage
=> risks/sourceLineage.risks += text_contamination_possible
=> sourceLineage.rejectedLineageReason=text_owned_rejected_lineage
=> sourceLineage.conflictClass=text_owned_rejected_lineage
=> sourceLineage.survivingPreOcrSymbolCandidate=false

high OCR overlap + surviving lineage + no strong text counter-evidence
=> mixed_symbol_text_candidate
=> decision=uncertain
=> sourceLineage preserved
```

M29.0.7 只做审计字段透传：

```text
text_noise + sourceLineage.conflictClass=text_owned_rejected_lineage
=> ownership=text_owned when OCR overlap/confidence supports it
=> visual side disallowed
=> reasons += text_owned_rejected_lineage
=> sourceLineage copied into ownershipDecision
```

M29.1.3 仍然是 audit-only，并且只处理收紧后剩余的 `mixed_symbol_text_candidate`。它不是下游 routing 输入。

## Text Counter-Evidence

第一版只使用已有证据，不新增 detector、不新建 bbox、不从 raw pixels 新切 child：

```text
M29.0.2 OCR/textBoxes
M29.1 sourceLineage/group/candidate metadata
M29.0.3 current mediaEvidence bbox
existing bbox geometry/overlap/metrics
```

固定文字反证：

```text
rejectedLineageReason == text_like_glyph_sequence
full OCR coverage >= 0.72
single char / digit / punctuation / price / unit OCR token
very wide or text-like aspect >= 3.5
glyph sequence risk from M29.1 candidate baseline alignment
lineageStrength=weak and lineageSource=eligible_blocked with high OCR overlap
```

`preOcrSymbolCandidate` 是历史事实，不应被抹掉。M29.0.3.1 通过 `survivingPreOcrSymbolCandidate=false` 表示该 lineage 不再作为 surviving visual lineage 进入 mixed 桶。

## Boundaries

- 不改 baseline M29.0.3。
- 不改 M29.1 group/candidate 输出。
- 不改 M29.0.4/M29.0.5 行为。
- 不做 M29.1.4。
- 不做 controlled promotion。
- 不恢复图标。
- 不生成 formal visual asset。
- 不把 mixed 放进 object-forming visual side。
- 不新增 bbox。
- 不从 raw pixels 新切 child。
- 不调 text overlap 阈值。
- 不让 M29.1.3 变成 routing 输入。

M29 前的视觉实验路径在本阶段只做文档降级，不删代码：

```text
M20-M28: legacy experiments / diagnostic references
OCR: 保留为 text ownership source
M29+: 当前正式主线
```

后续判断默认从 OCR + M29+ evidence 开始，不再把旧 icon/slice/SAM/business candidate harness 当主链路事实来源。

## Implementation

- 更新 `backend/app/visual_evidence_normalization.py`：
  - 收集 M29.0.2 `textBoxes` 作为 M29.0.3 text counter-evidence。
  - 在 lineage-aware high overlap 分支中先执行 `text_owned_rejected_lineage` gate。
  - 对 rejected lineage 保留 sourceLineage，并新增 `survivingPreOcrSymbolCandidate=false`、`conflictClass`、`counterEvidence`。
  - 将 M29.1 candidate bbox 附到 lineage lookup 中，用于 baseline glyph sequence risk。
- 更新 `backend/app/text_visual_ownership_gate.py`：
  - `OwnershipDecision` 可透传 `sourceLineage`。
  - rejected-lineage `text_noise` 保持 text-owned routing，只增加审计原因/风险。
- 更新测试：
  - M29.0.3 baseline/no-lineage/mixed/rejected-lineage path。
  - M29.0.7 rejected-lineage metadata propagation。
  - M29.1.3 只处理剩余 mixed，不处理 rejected-lineage text_noise。

## Validation

Focused：

```bash
cd backend && uv run pytest \
  tests/test_visual_evidence_normalization.py \
  tests/test_text_visual_ownership_gate.py \
  tests/test_mixed_symbol_text_conflict_audit.py -q
```

M29 focused：

```bash
cd backend && uv run pytest \
  tests/test_pre_ocr_symbol_lineage_audit.py \
  tests/test_symbol_fragment_grouping.py \
  tests/test_visual_evidence_normalization.py \
  tests/test_text_visual_ownership_gate.py \
  tests/test_visual_object_candidate_audit.py \
  tests/test_text_aware_visual_object_refinement.py \
  tests/test_member_boundary_quality_audit.py \
  tests/test_mixed_symbol_text_conflict_audit.py -q
```

Full：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
git status --short
```

已完成验证：

```text
cd backend && uv run pytest ...visual_evidence_normalization/text_visual_ownership_gate/mixed_symbol_text_conflict_audit -q
=> 32 passed

cd backend && uv run pytest ...M29 focused suite... -q
=> 84 passed

cd backend && uv run pytest
=> 296 passed

pnpm run check
=> passed

git diff --check
=> passed
```

## Batch Acceptance

在新的 timestamped batch root 上复跑，不覆盖旧结果。目标链路：

```text
M29
-> M29.1
-> M29.1.1 audit
-> M29.0.2
-> M29.0.3 --m291-lineage-json with text-rejected gate
-> M29.0.7
-> M29.0.4 --m2907-ownership-json
-> M29.0.5
-> M29.0.6
-> M29.1.3 audit remaining mixed
```

验收指标：

```text
mixed_symbol_text_candidate 从 4063 大幅下降
text_noise 合理回升
M29.0.3 text_owned_rejected_lineage count 接近当前 M29.1.3 textRejectedCount=4029
M29.0.7 bad routing 仍为 0
visualAssets 仍约 504，不暴涨
visualAssets text fragment risk 仍为 0
textMembers 仍约 741，不丢
weakTextNoiseUnresolvedRatio 仍为 0.0 或不反弹
future_promotable examples 仍可审计
keep_mixed examples 仍可审计
```

无效信号：

```text
mixed 不下降
visualAssets 暴涨
文字碎片回流 visualAssets
M29.0.7 bad routing > 0
weakTextNoiseUnresolvedRatio 反弹
future_promotable 被直接 promotion
M29.0.4/M29.0.5 直接消费 M29.1.3 输出
```

实测 batch root：

```text
backend/storage/m29_0_3_1_text_rejected_gate_batch_20260519_175032
```

实测结果：

```text
M29.0.3 old mixed_symbol_text_candidate: 4063
M29.0.3 new mixed_symbol_text_candidate: 44
M29.0.3 new text_noise: 4105
M29.0.3 text_owned_rejected_lineage: 4019
M29.0.7 bad mixed routing: 0
M29.0.5 visualAssets/textMembers: 504 / 741
M29.0.6 maxWeakTextNoiseRatio: 0.0
M29.1.3 remaining mixed classification: future=16, keep=10, textRejected=18
```

结论：M29.0.3.1 已把明显文字反证前移到 M29.0.3，mixed bucket 从 4063 收缩到 44；下游 visual asset、text member 和 ownership routing 未污染。剩余 44 个 mixed 继续交给 M29.1.3 audit-only 分类，不进入 routing 或 formal asset。
