# M29.0.3.2 80-Image Residual Mixed Boundary Acceptance

- 状态：active
- 创建日期：2026-05-19
- 负责人：Codex

## Goal

本阶段只做 80 图扩展 batch acceptance，不改分类规则、不改 routing、不做 promotion、不恢复图标。

目标是用两个 40 图目录跑完整 OCR + M29+ 证据链，得到 M29.0.3.2 residual mixed 的真实分布，再决定后续优先规划：

```text
M29.1.3.1 Future Candidate Strictness Calibration
```

或：

```text
M29.0.3.3 Residual Text Counter-Evidence Tightening
```

输入目录：

```text
/Users/luhui/Downloads/测试/images      40 PNG
/Users/luhui/Downloads/测试/images 2    40 PNG
```

## Invalid Evidence

batch root `backend/storage/m29_0_3_2_residual_mixed_boundary_review_batch_20260519_193713` 是无效验收证据，不得用于 M29.0.3.2 分布判断。

无效原因：

```text
M29.0.2 textSource = ocr_provider:baidu_ppocrv5:failed
warnings = BAIDU_PADDLE_OCR_TOKEN_MISSING
textBoxes = 0
```

根因是 batch runner 启动进程未加载仓库根目录 `.env.local`，导致百度 OCR token 没进入子进程环境。M29.0.2 单图 smoke 已验证：默认加载 `.env.local` 后，同一张图可得到 `textBoxes=79`。

## Run

执行：

```bash
cd backend
uv run python scripts/run_m29_0_3_2_residual_mixed_boundary_review.py --full-batch
```

runner 默认行为：

```text
读取 /Users/luhui/Downloads/测试/images
读取 /Users/luhui/Downloads/测试/images 2
按路径字典序排序
输出 image_001 ... image_080
创建 backend/storage/m29_0_3_2_residual_mixed_boundary_review_batch_YYYYMMDD_HHMMSS
```

每张图完整链路：

```text
M29
-> M29.1
-> M29.1.1
-> M29.0.2 with baidu_ppocrv5 OCR
-> M29.0.3 with M29.0.3.1 gate
-> M29.0.7
-> M29.0.4 with M29.0.7 ownership
-> M29.0.5
-> M29.0.6
-> M29.1.3
-> M29.0.3.2
```

如果百度 OCR token 缺失，runner 必须 fail fast，不创建新的 batch root，不生成 `textBoxes=0` 的假验收结果。

## Diagnostic Outputs

batch root 下生成：

```text
m29_0_3_2_batch_summary.json
m29_0_3_2_batch_summary.csv
m29_0_3_2_contact_sheet.png
m29_0_3_2_deduped_residual_summary.json
m29_0_3_2_text_heavy_future_summary.json
```

如果现有 runner 不直接生成 contact sheet / deduped summary / text-heavy future summary，则用一次性只读 Python 分析当前 batch root 生成这些 storage 诊断文件，不改 repo 代码。

分析口径必须是通用证据，不写页面或业务特化词：

```text
dedup key:
  same image + same bbox
  or same image + IoU >= 0.85 overlapping bbox

text-heavy future:
  reviewConclusion == candidate_for_future_uncertain_review
  and any of:
    fullOcrCoverage == true
    ocrCoverageKind == multiple_text_overlap
    textLikeToken == true
    textLikeAspectRisk == true
    glyphSequenceRisk == true
    m2913Classification == text_owned_rejected_lineage
```

只做统计和抽样，不改变任何上游 JSON。

## Acceptance

batch 必须记录：

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
ocrCompletedImages
ocrFailedImages
totalOcrTextBoxes
```

硬验收：

```text
completedImages + failedImages = 80
ocrFailedImages = 0
totalOcrTextBoxes > 0
totalBadRouting = 0
all permission flags false
visualAssets 不异常暴涨
textMembers 仍存在且不明显丢失
maxWeakTextNoiseRatio 不反弹
forbidden terms absent
每个 completed image 有 M29.0.3.2 JSON/MD/review sheet
```

分布判断指标：

```text
dedupedResidualMixedCount
rawToDedupResidualRatio
textHeavyFutureCandidateCount
textHeavyFutureCandidateRatio
tighteningCandidateRatio
futureReviewCandidateRatio
keepResidualMixedRatio
```

## Result - 2026-05-19 Valid Batch

有效 batch root：

```text
backend/storage/m29_0_3_2_residual_mixed_boundary_review_batch_20260519_200727
```

上一轮无效 batch 仍然不得引用为 acceptance 结论：

```text
backend/storage/m29_0_3_2_residual_mixed_boundary_review_batch_20260519_193713
reason: BAIDU_PADDLE_OCR_TOKEN_MISSING, textBoxes=0
```

有效 batch 总量：

```text
totalImages: 80
completedImages: 80
failedImages: 0
partialFailureCount: 0
totalResidualMixed: 156
totalTighteningCandidates: 103
totalM2913AdjustmentCandidates: 0
totalFutureReviewCandidates: 37
totalKeepResidualMixed: 16
totalInsufficientEvidence: 0
maxWeakTextNoiseRatio: 0.0
totalBadRouting: 0
totalVisualAssets: 2898
totalTextMembers: 4880
```

OCR 验证：

```text
ocrCompletedImages: 80
ocrFailedImages: 0
totalOcrTextBoxes: 6097
minOcrTextBoxes: 51
maxOcrTextBoxes: 135
avgOcrTextBoxes: 76.2125
```

扩展诊断：

```text
dedupedResidualMixedCount: 134
rawToDedupResidualRatio: 1.164179
textHeavyFutureCandidateCount: 4
textHeavyFutureCandidateRatio: 0.108108
permissionViolationCount: 0
missingReviewOutputCount: 0
forbiddenHitCount: 0
```

storage-only 诊断产物：

```text
m29_0_3_2_contact_sheet.png
m29_0_3_2_deduped_residual_summary.json
m29_0_3_2_text_heavy_future_summary.json
```

第一性原理结论：

```text
这才是第一轮有效 OCR + M29+ 80 图 acceptance。
193713 batch 是 OCR 缺 token 导致的假证据，不能用于 mixed 分布判断。
当前最大残留类是 m2903_tightening_candidate: 103 / 156。
下一步更可能优先审查 M29.0.3.3 Residual Text Counter-Evidence Tightening，
但必须先看 evidence examples；本阶段不改规则。
```

## Decision Rules After Batch

按事实分流：

```text
textHeavyFutureCandidateRatio 高
=> 下一阶段优先规划 M29.1.3.1 Future Candidate Strictness Calibration

tighteningCandidateRatio 高，且抽样确认大多是文字
=> 下一阶段优先规划 M29.0.3.3 Residual Text Counter-Evidence Tightening

keepResidualMixedRatio 高，且人眼也难判
=> 暂不改规则，只增强 audit/dedup/reporting

totalBadRouting > 0 或 visualAssets/textMembers 异常
=> 停止分类优化，先查主链路污染

ocrFailedImages > 0
=> 停止分类分布判断，先查 OCR provider / input coverage
```

## Boundaries

- 不改 M29.0.3。
- 不改 M29.1.3。
- 不改 M29.0.7。
- 不改 M29.0.4/M29.0.5。
- 不做 M29.1.4。
- 不做 controlled promotion。
- 不把 `candidate_for_future_uncertain_review` 放进 visual side。
- 不生成 formal visual asset。
- 不新增 bbox。
- 不从 raw pixels 新切 child。
- 不重新 detector。
- 不写页面、行业、业务特化规则。
- `backend/storage/**` 是 diagnostic artifact，不提交。

禁止输出特化或恢复语义词：

```text
bottom_nav
tab
toolbar
grid
ecommerce
education
coupon
course
delivery
recruiting
business icon
restore
icon recovery
```
