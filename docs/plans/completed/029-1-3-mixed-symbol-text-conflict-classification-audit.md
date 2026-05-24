# M29.1.3 Mixed Symbol/Text Conflict Classification Audit

- 状态：completed
- 创建日期：2026-05-19
- 负责人：Codex

## Goal

M29.1.3 是 M29+ 的 script-only、audit-only 分类阶段。它只处理 M29.0.3 `visual_evidence.json` 中 `visualKind == mixed_symbol_text_candidate` 的候选，把 mixed 冲突桶拆成可审计的三类：

```text
future_promotable_uncertain_symbol_candidate
keep_mixed_symbol_text_conflict
text_owned_rejected_lineage
```

当前 lineage-aware batch comparison 显示：

```text
mixed_symbol_text_candidate: 4063
avg mixed ratio: 0.838089
max mixed ratio: 0.900915
bad mixed routing: 0
visualAssets: 504 -> 504
textMembers: 741 -> 741
weakTextNoiseUnresolvedRatio max: 0.0
```

这说明 M29.1.1/M29.1.2 没有污染主链路，但 mixed 桶很大。M29.1.3 的目标不是恢复图标，而是降低 mixed 桶的不确定性，先证明哪些候选未来值得审查、哪些继续保持冲突、哪些虽然有 lineage 但应归 text ownership。

## Contract

Primary universe：

```text
M29.0.3 visual_evidence.json
where item.visualKind == mixed_symbol_text_candidate
```

其他输入只作为 lookup / evidence reference：

```text
M29.0.7 text_visual_ownership_gate.json
M29.1 group_nodes.json
M29.1.1 pre_ocr_symbol_lineage_audit.json
M29.0.2 text_masked_media_audit.json
source PNG
```

source PNG 只能用于：

```text
裁 existing bbox examples
画 overlay
计算 existing bbox crop 的简单 audit metrics
```

输出：

```text
m29_1_3/mixed_symbol_text_conflict_audit.json
m29_1_3/mixed_symbol_text_conflict_audit.md
m29_1_3/overlay_mixed_symbol_text_conflicts.png
m29_1_3/assets/future_promotable_examples/
m29_1_3/assets/keep_mixed_examples/
m29_1_3/assets/text_owned_rejected_examples/
m29_1_3_batch_summary.json
m29_1_3_batch_summary.csv
```

所有 example images 都是 audit evidence crops，不是 assets，不能被后续 `visualAssets` 消费。

Document schema：

```text
M2913MixedSymbolTextConflictAuditDocument v0.1
```

每条 conflict 必须记录：

```text
id
sourceVisualEvidenceItemId
sourceEvidenceId
sourceM291GroupId
sourceM291CandidateIds
sourceM2911FindingIds
sourceM2907OwnershipDecisionId
bbox
classification
classificationConfidence
promotionRisk
textContaminationRisk
allowedForCurrentPromotion
allowedForObjectFormingVisualSide
allowedForFormalVisualAsset
allowedForRoutingChange
signals
reasons
risks
exampleAssetPaths
```

以下 downstream permission flags 必须始终为 `false`：

```text
allowedForCurrentPromotion
allowedForObjectFormingVisualSide
allowedForFormalVisualAsset
allowedForRoutingChange
```

## Classification

默认规则：

```text
unknown -> keep_mixed_symbol_text_conflict
```

偏向 `text_owned_rejected_lineage`：

```text
full_ocr_coverage
glyph_sequence_risk
text_like_glyph_sequence finding
very_wide_or_text_like_aspect
OCR match is single char / digit / punctuation / price / unit
many tiny strokes aligned on same text baseline
lineageStrength=weak and lineageSource=eligible_blocked
```

偏向 `future_promotable_uncertain_symbol_candidate`：

```text
lineageStrength=strong or medium
lineageSource=m291_group or m29_symbol
compact geometry
partial OCR overlap, not full coverage
not glyph sequence
repeated compact alignment
label-adjacent relation
visual structure hint
duplicate topology suggests repeated symbol-like pattern
```

偏向 `keep_mixed_symbol_text_conflict`：

```text
signals conflict
lineage weak
OCR overlap substantial
no repeated compact alignment
no clear label-adjacent relation
not clearly glyph-like
not clearly symbol-like
```

`future_promotable_uncertain_symbol_candidate` 只表示 future human-review candidate。它不能进入 visual side，不能生成 formal visual asset，不能触发 M29.1.4 行为。

## Boundaries

- 不改 M29.0.3。
- 不改 M29.0.7。
- 不改 M29.0.4。
- 不改 M29.0.5。
- 不做 promotion。
- 不恢复图标。
- 不生成 formal visual asset。
- 不把 mixed 放进 object-forming visual side。
- 不新增 bbox。
- 不从 raw pixels 新切 child。
- 不调 text overlap 阈值。
- 不写页面角色或行业特化合同。
- M29.1.4 明确 out of scope。

禁止新增特化或恢复语义词：

```text
bottom_nav
tab
toolbar
grid
ecommerce
education
recoverable_icon
promotable_icon
icon_recovery
restore
```

## Run

```bash
cd backend
uv run python scripts/run_m29_1_3_mixed_symbol_text_conflict_audit.py \
  --input "/path/to/source.png" \
  --m29-output storage/m29_lineage_aware_batch_comparison_20260519_155657/image_02
```

默认解析：

```text
latest m29_0_3*/visual_evidence.json
latest m29_0_7*/text_visual_ownership_gate.json
latest m29_1*/group_nodes.json
latest m29_1_1*/pre_ocr_symbol_lineage_audit.json
latest m29_0_2*/text_masked_media_audit.json
```

如果输出目录已存在且未传 `--overwrite`，脚本自动写入时间戳后缀目录。

## Validation

Focused：

```bash
cd backend && uv run pytest tests/test_mixed_symbol_text_conflict_audit.py -q
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
```

## Acceptance

- 只有 `mixed_symbol_text_candidate` item 会变成 conflicts。
- 非 mixed M29.0.3 items 被忽略。
- unknown signals 默认进入 `keep_mixed_symbol_text_conflict`。
- full OCR coverage + glyph sequence risk 进入 `text_owned_rejected_lineage`。
- `text_like_glyph_sequence` finding 进入 `text_owned_rejected_lineage`。
- strong/medium lineage + compact + partial OCR + not glyph-like 可进入 `future_promotable_uncertain_symbol_candidate`。
- conflicting signals 进入 `keep_mixed_symbol_text_conflict`。
- 所有 downstream permission flags 都是 `false`。
- source PNG 只生成 existing-bbox examples 和 overlay。
- example crops 是 audit evidence，不是 formal assets。
- 不新增 bbox，不改写 M29.0.3/M29.0.7/M29.0.4/M29.0.5。
- overlay PNG 可读且尺寸等于源图。
- batch summary 包含 10 张分类总量和 example counts。
- 输出 JSON/MD/reason/risk/classification 不包含 forbidden terms。

## Implementation Evidence

- 新增 `backend/app/mixed_symbol_text_conflict_audit.py`，输出 `M2913MixedSymbolTextConflictAuditDocument v0.1`。
- 新增 `backend/scripts/run_m29_1_3_mixed_symbol_text_conflict_audit.py`，支持单图和 `--batch-root`。
- 新增 `backend/tests/test_mixed_symbol_text_conflict_audit.py`，覆盖 primary universe、三类分类、downstream permission flags、overlay/example crops、batch summary 和 forbidden terms。
- 同步 `backend/README.md`、`docs/index.md`、`docs/engineering/testing-strategy.md`。

Focused validation：

```text
cd backend && uv run pytest tests/test_mixed_symbol_text_conflict_audit.py -q
10 passed
```

M29 focused validation：

```text
cd backend && uv run pytest tests/test_pre_ocr_symbol_lineage_audit.py tests/test_symbol_fragment_grouping.py tests/test_visual_evidence_normalization.py tests/test_text_visual_ownership_gate.py tests/test_visual_object_candidate_audit.py tests/test_text_aware_visual_object_refinement.py tests/test_member_boundary_quality_audit.py tests/test_mixed_symbol_text_conflict_audit.py -q
79 passed
```

10-image smoke：

```text
cd backend
uv run python scripts/run_m29_1_3_mixed_symbol_text_conflict_audit.py \
  --batch-root storage/m29_lineage_aware_batch_comparison_20260519_155657
```

Smoke summary：

```text
mixedCount: 4063
futurePromotableCount: 24
keepMixedCount: 10
textRejectedCount: 4029
badRoutingCountFromM2907: 0
visualAssetCountFromM2905: 504
max weakTextNoiseRatioFromM2906: 0.0
all downstream permission flags: false
```
