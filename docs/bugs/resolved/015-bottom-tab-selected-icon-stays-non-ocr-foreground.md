# Bug: Bottom tab selected icon stays non-OCR foreground

- 状态：resolved
- 创建日期：2026-05-26
- 解决日期：2026-05-26
- 影响范围：M29.6 media internal decomposition、M29.2 source ownership、transparent asset gate、M29 evidence contract、internal source promotion、M29.5 replay plan、ownership conservation

## Summary

最新资产样本中，底部 tab 已经恢复大部分图标，但 selected tab icon 仍未成为独立 icon layer；同时 selected label 下方的横向 indicator 被误当成 `standalone_symbol_icon`。

当前失败不是 OCR 问题。底部 5 个 tab label 都已 OCR 并进入 text replay。失败点是选中态 tab item 内部角色没有分清：

```text
selected tab item =
  icon
  + label text
  + selected indicator
  + selected background/glow
```

## Reproduction

当前 task：

```text
task_0adc84a2a7b9
```

关键证据：

```text
M29.2:
  首页/市场/交易/我的 icon -> raster_icon / icon_replay
  selected tab icon -> no raster_icon source object

M29.6:
  m292_object_0094:internal_candidate_0014
  bbox = [602,1546,73,67]
  rawSubtype = non_ocr_foreground
  decision = accepted_report_candidate
  confidence = medium
  matchedOcrBoxId = null

Transparent:
  sourceObjectId = m292_object_0094:internal_candidate_0014
  decision = reject
  reason = internal_candidate_not_execution_supported

M29.2 false icon:
  m292_object_0112
  bbox = [609,1650,73,17]
  reason = standalone_symbol_icon
  finalReplayAction = icon_replay
```

## Root Cause

M29.6 对 media 内 OCR label 归属使用严格 containment，导致轻微越过 parent media 下沿的 tab label 没进入 `text_inside`。因此 `资产` icon 虽被像素 foreground 检出，却无法绑定到 label anchor，也无法获得 group-supported execution。

另一个根因是 M29.2 icon clustering 把 label 下方的横向选中 indicator 当成 standalone icon。

修复 anchor 后又暴露出两个后续门：

```text
transparent asset:
  selected-state icon 带 soft glow，默认 edge-alpha gate 把它当脏边拒绝。

evidence contract:
  anchored `pixel_component/non_ocr_foreground` 仍被一刀切当 generic foreground 拒绝。

M29.5 / ownership conservation:
  promoted internal icon 与 parent media、label bbox 和 near-equal promoted candidate 的关系需要可解释去重/守恒。
```

第一性原理链路：

```text
real goal:
  selected bottom tab 的 icon、label、indicator 应分角色进入证据链。

source truth:
  source PNG pixels + OCR label bbox + raw M29 symbol/blocked/pixel evidence。

information-loss point:
  tab item 结构被压成散乱 foreground，selected indicator 与 icon 竞争同一角色。

owning layer:
  M29.6 OCR anchor attribution and M29.2 source ownership icon classifier。

do-not-do:
  不按文字、坐标、颜色、task id、文件名特化；
  不在 materializer/Renderer/plugin 发明 missing icon；
  不放宽全局 non-OCR foreground execution gate。
```

## Fix

已修复：

1. M29.6 允许 OCR label 通过 near-media context 参与 internal anchor，而不是只看 0.95 containment。
2. M29.6 对 `non_ocr_foreground` 做 label-anchor recovery；若 icon 与 label 在同一 media context 中几何关系成立，则写入 `matchedOcrBoxId` 和 directional relation。
3. M29.2 识别 label 下方、横向、宽度接近 label、明显 thin 的 selected indicator，禁止其进入 standalone icon replay。第一版保守降为 diagnostic 或由 shape 逻辑接管。
4. Transparent asset report 新增 `anchored_soft_edge_icon` profile。只有强 OCR anchor、group support、低 text overlap、低 hero penalty 的 M29.6 internal icon 才允许 soft edge alpha 通过。
5. Evidence contract 对 `pixel_component/non_ocr_foreground` 的硬拒绝改成只拒绝未锚定/无 group support 的 generic foreground。
6. M29.5 对 near-equal promoted internal icons 按 evidenceScore 保留最强候选；对 promoted internal icon 与 low text-overlap label bbox overlap 不再误 suppress。
7. Ownership conservation 将同一 parent media 内、双方都有 copied image cleanup target 且 promoted icon `textOverlapRatio` 低的 icon/text overlap 视为可解释 owner relation。

## Regression Guard

- `test_near_media_bottom_label_can_anchor_internal_icon_candidate`
- `test_selected_tab_indicator_symbol_is_not_standalone_icon`
- `test_anchored_group_supported_internal_icon_allows_soft_edge_glow`
- `test_unanchored_internal_icon_with_soft_edge_still_rejects_edge_alpha_risk`
- `test_anchored_group_supported_non_ocr_foreground_can_pass_evidence_contract`
- `test_anchored_non_ocr_foreground_without_group_support_stays_rejected`
- `test_m295_keeps_higher_evidence_promoted_internal_icon_for_near_equal_candidates`
- `test_m295_keeps_promoted_internal_icon_with_low_label_bbox_overlap`
- `test_promoted_internal_icon_low_label_overlap_is_explainable_when_both_cleanup_same_media`
- `test_promoted_internal_icon_high_label_overlap_is_still_reported`

## Validation Evidence

Core regression：

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py tests/test_source_ui_physical_graph.py tests/test_transparent_asset_report.py tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py tests/test_upload_preview_pipeline.py -q
```

结果：

```text
125 passed in 17.23s
```

真实样本复跑：

```text
source task = task_0adc84a2a7b9
rerun task = task_144694879ab0
ledger = backend/tmp/validation/upload_preview_batch_20260526_141939/upload_preview_batch_validation.json
```

Batch summary：

```text
completedTaskCount = 1
degradedRecordCount = 0
backendCrashCount = 0
totalVisibleOwnershipOverlapConflicts = 0
totalTransparentAssetAllowedCount = 24
totalPromotedInternalSourceObjectCount = 21
```

修复后关键证据：

```text
Transparent:
  sourceObjectId = m292_object_0094:internal_candidate_0019
  decision = allow
  alphaProfile = anchored_soft_edge_icon
  edgeAlphaCoverageGt32 = 0.2633
  largestComponentRatio = 0.9491

M29.5:
  m292_promoted_internal_icon_0020
  finalReplayAction = icon_replay
  targetRole = m29_symbol
  copied_image_asset cleanup target = m292_object_0094

Selected indicator:
  m292_object_0131
  finalReplayAction = diagnostic_only
  reason = selected_tab_indicator_not_icon

Ownership conservation:
  conflictCount = 0
```

## Prevention Notes

同类问题检查：

```text
OCR label 是否轻微越过 media bbox
internal candidate 是否只是 non_ocr_foreground 但与 label 有强几何关系
selected indicator 是否被当作 icon replay
transparent gate 拒绝原因是否是 internal_candidate_not_execution_supported
transparent gate 拒绝原因是否是 edge_alpha_risk，但候选是否具备 strong anchor + group support + low textOverlap
evidence contract 是否因为 generic_foreground_not_visible_replay 拒绝了已锚定、组支持的 internal icon
M29.5 是否把 promoted internal icon 与 label 轻微 bbox overlap 误判成 duplicate
```

不得用：

```text
literal label text
file name
task id
fixed bbox
fixed screen coordinate
theme color
app category
materializer hard patch
Renderer/plugin fallback
```
