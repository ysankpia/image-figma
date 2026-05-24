# M29.0.3.2 Residual Mixed Boundary Review

- 状态：completed
- 创建日期：2026-05-19
- 负责人：Codex

## Goal

M29.0.3.2 是 M29+ 的 script-only、actionable audit/review 阶段。它只解释 M29.0.3.1 收紧后仍残留的 `mixed_symbol_text_candidate`，不做 promotion，不恢复图标，不改变 routing，不生成 formal visual asset。

第一性原理判断：

```text
source fact: OCR/textBoxes 是 text ownership 的独立证据。
source fact: M29/M29.1 lineage 是 provenance，不是 asset permission。
current fact: M29.0.3.1 已把强文字反证前移，mixed 从 4063 降到 44。
remaining problem: 剩余 mixed 需要解释边界，而不是直接打开 visual side。
correct object: residual mixed review document，而不是 M29.0.4/M29.0.5 routing 补丁。
```

当前 10 图事实：

```text
old mixed_symbol_text_candidate: 4063
new mixed_symbol_text_candidate: 44
text_owned_rejected_lineage: 4019
M29.0.7 bad routing: 0
visualAssets/textMembers: 504 / 741
maxWeakTextNoiseRatio: 0.0
remaining M29.1.3: future=16, keep=10, textRejected=18
```

扩展样本策略：

```text
sample scope: /Users/luhui/Downloads/测试/images + /Users/luhui/Downloads/测试/images 2
expected image count: 80 PNGs
batch mode: new timestamped full lineage-aware batch
```

本阶段实现 batch runner 和 review 合同；80 图 full batch 是后续 smoke acceptance，不作为单元测试前置条件，且不得覆盖既有 storage 结果。

## Contract

Primary universe：

```text
M29.0.3 visual_evidence.json
where item.visualKind == mixed_symbol_text_candidate
```

Lookup/evidence refs：

```text
M29.1.3 mixed_symbol_text_conflict_audit.json
M29.0.7 text_visual_ownership_gate.json
M29.0.2 textBoxes / OCR evidence
M29.1 group_nodes.json
M29.1.1 pre_ocr_symbol_lineage_audit.json
source PNG
```

source PNG 只能用于：

```text
裁 existing bbox evidence crop
画 review sheet
计算 existing bbox crop audit metrics
```

禁止：

```text
不新增 bbox
不从 raw pixels 新切 child
不重新 detector
不改上游 JSON
不做 promotion
不生成 formal visual asset
不打开 visual side
不调 text overlap threshold
不写页面或行业特化合同
```

输出：

```text
m29_0_3_2/residual_mixed_boundary_review.json
m29_0_3_2/residual_mixed_boundary_review.md
m29_0_3_2/review_sheet_remaining_mixed.png
m29_0_3_2/assets/future_promotable_review/
m29_0_3_2/assets/keep_mixed_review/
m29_0_3_2/assets/text_rejected_review/
m29_0_3_2/assets/tightening_candidates/
m29_0_3_2/assets/insufficient_evidence/
m29_0_3_2_batch_summary.json
m29_0_3_2_batch_summary.csv
```

所有 `assets/` 下图片都是 audit evidence crops，不是 formal visual assets，也不能被后续 `visualAssets` 消费。

Document schema：

```text
M29032ResidualMixedBoundaryReviewDocument v0.1
```

每条 review item 必须记录：

```text
id
sourceImageId
sourceVisualEvidenceItemId
sourceM2913ConflictId
sourceM2907OwnershipDecisionId
bbox
m2913Classification
reviewConclusion
recommendedNextStage
shouldTightenM2903
shouldAdjustM2913
candidateForFutureUncertainReview
allowedForPromotionNow
allowedForVisualSideNow
allowedForFormalAssetNow
signals
reasons
risks
exampleCropPath
```

Permission flags 必须恒为 `false`：

```text
allowedForPromotionNow
allowedForVisualSideNow
allowedForFormalAssetNow
```

## Review Conclusions

固定五类：

```text
m2903_tightening_candidate
m2913_classification_adjustment_candidate
keep_residual_mixed_conflict
candidate_for_future_uncertain_review
insufficient_evidence
```

默认规则：

```text
unknown / conflicting signals
=> keep_residual_mixed_conflict
```

不能默认进入 future review，也不能默认进入 M29.0.3 tightening。

判定方向：

```text
m2903_tightening_candidate:
  M29.1.3 已判 text_owned_rejected_lineage
  且存在 M29.0.3 可读取的通用 text counter-evidence

m2913_classification_adjustment_candidate:
  M29.1.3 分类和底层信号明显冲突

candidate_for_future_uncertain_review:
  M29.1.3 classified future
  OCR overlap 非 full coverage
  not glyph-like
  compact / repeated / label-adjacent / visual structure 信号至少满足多个
  text contamination risk 不高

keep_residual_mixed_conflict:
  信号互相冲突
  既不明显归 text，也不够干净进入 future review

insufficient_evidence:
  缺少 M29.1.3、M29.0.7、OCR/textBoxes 或 lineage lookup，无法可靠判断
```

`m2903_tightening_candidate` 只是“可考虑前移规则”的审计建议，本阶段不改 M29.0.3。`candidate_for_future_uncertain_review` 只是未来可审查，不表示现在能 promotion。

## Runner

单图：

```bash
cd backend
uv run python scripts/run_m29_0_3_2_residual_mixed_boundary_review.py \
  --input "/path/to/source.png" \
  --m29-output storage/.../image_001
```

已有 batch：

```bash
cd backend
uv run python scripts/run_m29_0_3_2_residual_mixed_boundary_review.py \
  --batch-root storage/m29_0_3_1_text_rejected_gate_batch_YYYYMMDD_HHMMSS
```

80 图 full batch：

```bash
cd backend
uv run python scripts/run_m29_0_3_2_residual_mixed_boundary_review.py --full-batch
```

默认 full batch 输入目录：

```text
/Users/luhui/Downloads/测试/images
/Users/luhui/Downloads/测试/images 2
```

默认输出：

```text
backend/storage/m29_0_3_2_residual_mixed_boundary_review_batch_YYYYMMDD_HHMMSS
```

每张图的 full chain：

```text
M29
-> M29.1
-> M29.1.1 audit
-> M29.0.2
-> M29.0.3 --m291-lineage-json with M29.0.3.1 gate
-> M29.0.7
-> M29.0.4 --m2907-ownership-json
-> M29.0.5
-> M29.0.6
-> M29.1.3 audit remaining mixed
-> M29.0.3.2 residual mixed boundary review
```

如果某图失败，runner 记录 `imageId`、`sourceImage`、`failedStage`、`error`，继续下一张，并在 batch summary 标记 failure。

## Batch Summary

`m29_0_3_2_batch_summary.json/csv` 包含 image-level rows：

```text
imageId
sourceImage
residualMixedCount
m2903TighteningCandidateCount
m2913AdjustmentCandidateCount
keepResidualMixedCount
futureUncertainReviewCandidateCount
insufficientEvidenceCount
m2913FutureCount
m2913KeepCount
m2913TextRejectedCount
badRoutingCountFromM2907
visualAssetCountFromM2905
textMemberCountFromM2905
weakTextNoiseRatioFromM2906
failedStage
error
```

batch totals：

```text
totalImages
completedImages
failedImages
partialFailureCount
totalResidualMixed
totalTighteningCandidates
totalM2913AdjustmentCandidates
totalFutureReviewCandidates
totalKeepResidualMixed
totalInsufficientEvidence
maxWeakTextNoiseRatio
totalBadRouting
totalVisualAssets
totalTextMembers
```

## Boundaries

- M29.1.4 out of scope。
- M29.1.3 仍是 audit-only。
- M29.0.4/M29.0.5/M29.0.7 不消费 M29.0.3.2 输出。
- M29.0.3.2 不修改 M29.0.3/M29.0.7/M29.0.4/M29.0.5 输出。
- 不做 promotion。
- 不恢复图标。
- 不生成 formal visual asset。
- 不把 mixed 放进 object-forming visual side。
- 不新增 bbox。
- 不从 raw pixels 新切 child。
- 不调 text overlap threshold。
- 不写页面角色或行业特化合同。
- example crops 只是 evidence，不是 `visualAssets`。

M20-M28 继续保持 legacy diagnostic reference。OCR + M29+ 是当前正式证据链。

禁止输出特化或恢复语义词：

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

## Validation

Focused：

```bash
cd backend && uv run pytest tests/test_residual_mixed_boundary_review.py -q
```

M29 focused：

```bash
cd backend && uv run pytest \
  tests/test_visual_evidence_normalization.py \
  tests/test_text_visual_ownership_gate.py \
  tests/test_mixed_symbol_text_conflict_audit.py \
  tests/test_residual_mixed_boundary_review.py -q
```

Full：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

## Acceptance

- 只有 M29.0.3 `mixed_symbol_text_candidate` items 会变成 review items。
- 非 mixed M29.0.3 items 被忽略。
- 缺少 M29.1.3 conflict 进入 `insufficient_evidence`。
- M29.1.3 `text_owned_rejected_lineage` + M29.0.3-readable text signals 进入 `m2903_tightening_candidate`。
- M29.1.3 future + high text-like risk 进入 `m2913_classification_adjustment_candidate`。
- M29.1.3 future + compact/partial/not-glyph/repeated or label relation 进入 `candidate_for_future_uncertain_review`。
- conflicting / unknown signals 进入 `keep_residual_mixed_conflict`。
- 所有 permission flags 都是 `false`。
- example crops 是 evidence only，不是 formal visual assets。
- 不新增 bbox。
- review sheet 可读且等于源图尺寸。
- forbidden terms check 生效。
- batch summary 包含 image-level 和 total counts。
- partial image failure 不会中断整个 batch。

## Implementation Evidence

- 新增 `backend/app/residual_mixed_boundary_review.py`。
- 新增 `backend/scripts/run_m29_0_3_2_residual_mixed_boundary_review.py`。
- 新增 `backend/tests/test_residual_mixed_boundary_review.py`。
- 同步 `backend/README.md`、`docs/index.md`、`docs/architecture/backend.md`、`docs/engineering/testing-strategy.md`。

Focused validation：

```text
cd backend && uv run pytest tests/test_residual_mixed_boundary_review.py -q
10 passed
```

M29 focused validation：

```text
cd backend && uv run pytest tests/test_visual_evidence_normalization.py tests/test_text_visual_ownership_gate.py tests/test_mixed_symbol_text_conflict_audit.py tests/test_residual_mixed_boundary_review.py -q
42 passed
```

Full validation：

```text
cd backend && uv run pytest
306 passed

pnpm run check
passed

git diff --check
passed
```

10-image smoke on existing M29.0.3.1 batch:

```text
cd backend
uv run python scripts/run_m29_0_3_2_residual_mixed_boundary_review.py \
  --batch-root storage/m29_0_3_1_text_rejected_gate_batch_20260519_175032 \
  --overwrite
```

Smoke summary:

```text
totalImages: 10
completedImages: 10
failedImages: 0
totalResidualMixed: 44
totalTighteningCandidates: 18
totalM2913AdjustmentCandidates: 0
totalFutureReviewCandidates: 16
totalKeepResidualMixed: 10
totalInsufficientEvidence: 0
maxWeakTextNoiseRatio: 0.0
totalBadRouting: 0
totalVisualAssets: 504
totalTextMembers: 741
```
