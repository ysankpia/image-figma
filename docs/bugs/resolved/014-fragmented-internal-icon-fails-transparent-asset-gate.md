# Bug: 图内 UI icon 被拆成碎片后不能通过透明资产门禁

- 状态：resolved
- 创建日期：2026-05-26
- 解决日期：2026-05-26
- 影响范围：M29.6 media internal decomposition、M29 transparent asset report、M29 evidence contract、internal source promotion、M29.5 replay plan

## Summary

真实资产总览截图中，轮播/资产卡片 action row 的四个入口：

```text
充值 / 提币 / 划转 / 买币
```

已经能识别出三个 icon，但 `划转` 上方 icon 没有成为独立 Figma image layer。

这不是 OCR 问题。`划转` 文本已经由 OCR 识别，且 M29.6 已经找到了它上方的 icon foreground。真正问题是该 icon 在 raw/internal candidate 层被切成上下两个相邻碎片：

```text
top fragment    -> [547, 544, 45, 25]
bottom fragment -> [545, 567, 46, 20]
```

下半截单独进入 transparent asset gate 时，主体贴近 crop 边缘，触发 `edge_alpha_risk`，所以 evidence contract 只能给 `report_only`，最终没有 internal source promotion，也就没有 M29.5 `icon_replay`。

## Reproduction

复现 task：

```text
task_8139d920573e
```

关键 artifact：

```text
backend/storage/upload_previews/task_8139d920573e/ocr/ocr.json
backend/storage/upload_previews/task_8139d920573e/m29_media_internal_decomposition/media_internal_decomposition_report.json
backend/storage/upload_previews/task_8139d920573e/m29_transparent_assets/transparent_asset_report.json
backend/storage/upload_previews/task_8139d920573e/m29_evidence_contract/evidence_contract_report.json
backend/storage/upload_previews/task_8139d920573e/m29_internal_source_promotion/internal_source_promotion_report.json
backend/storage/upload_previews/task_8139d920573e/m29_5/replay_plan.json
```

`划转` OCR：

```text
ocr_text_015
text = 划转
bbox = [543, 606, 49, 28]
confidence = 0.9999
```

失败前证据：

```text
m292_object_0084:internal_candidate_0036
  bbox = [547, 544, 45, 25]
  matchedOcrBoxId = ocr_text_015
  transparent asset = reject
  reason = internal_candidate_not_execution_supported

m292_object_0084:internal_candidate_0037
  bbox = [545, 567, 46, 20]
  matchedOcrBoxId = ocr_text_015
  transparent asset = reject
  reason = edge_alpha_risk
  edgeAlphaMean = 55.78
  edgeAlphaCoverageGt32 = 0.22
```

诊断实验显示，把两个碎片 union 成 `[545, 544, 47, 43]` 后，transparent asset gate 可以通过：

```text
decision = allow
analysisBbox = [533, 532, 71, 67]
edgeAlphaMean = 0.0
edgeAlphaCoverageGt32 = 0.0
```

## Root Cause

根因是 M29.6 只把单个 raw/pixel component 当作 icon candidate，没有形成同一 OCR anchor 下的 complementary fragment union candidate。

第一性原理判断：

```text
real goal:
  图内 action row icon 应该在证据支持时成为独立 selectable image/icon layer。

source truth:
  source PNG pixels + OCR label bbox + raw M29 symbol/pixel components + M29.6 candidate evidence + transparent alpha analysis。

information-loss point:
  一个视觉 icon 被局部 foreground/raw symbol evidence 切成多个相邻 fragments；
  单碎片 crop 不再代表完整 icon，因此 transparent alpha edge gate 会误判。

owning layer:
  M29.6 media internal decomposition candidate generation。

do-not-do:
  不在 materializer / Renderer / plugin 按文字、坐标或样本补 icon。
  不放宽 global edge_alpha_risk 门禁。
```

## Fix

在 M29.6 candidate 层新增通用合并：

```text
same media
+ same OCR anchor
+ same directional anchor relation
+ both accepted internal icon candidates
+ nearby / overlapping along the icon axis
+ union bbox still finite icon-like
+ no text mask conflict
=> merged_anchor_icon_fragments candidate
```

合并 candidate 仍然只是 M29.6 report evidence，不直接创建 DSL、资产、visible node 或 cleanup 权限。它必须继续经过：

```text
transparent asset report
-> evidence contract
-> internal source promotion
-> M29.3/M29.4/M29.5 final reports
-> plan materializer
```

## Regression Guard

新增回归测试：

```text
tests/test_media_internal_decomposition.py::test_fragmented_icon_parts_with_same_text_anchor_get_union_candidate
```

覆盖：

```text
三个正常 icon + 一个被上下切开的 icon
同一 OCR anchor 下生成 merged_anchor_icon_fragments
merged candidate bbox 是 fragment union
merged candidate 保持 groupSupportedExecution
matched action row 仍覆盖四个 text anchors
不依赖文字内容、文件名、主题色、坐标或单截图结构
```

## Validation Evidence

Focused tests：

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py -q

uv run pytest \
  tests/test_media_internal_decomposition.py \
  tests/test_transparent_asset_report.py \
  tests/test_m29_evidence_contract.py \
  tests/test_internal_source_promotion.py \
  tests/test_m29_replay_plan.py \
  tests/test_m29_plan_materializer.py \
  tests/test_upload_preview_pipeline.py \
  -q
```

结果：

```text
12 passed
78 passed
```

复跑真实图：

```text
source task = task_8139d920573e
rerun task = task_0adc84a2a7b9
```

修复后 `划转` 证据：

```text
M29.6 candidate:
  id = m292_object_0084:internal_candidate_0080
  rawType = merged_fragment
  bbox = [545, 544, 47, 43]
  matchedOcrBoxId = ocr_text_015
  confidence = high
  score = 0.744
  reasons = [merged_anchor_icon_fragments, text_anchor_geometry]
  sourceFragmentCandidateIds =
    m292_object_0084:internal_candidate_0037
    m292_object_0084:internal_candidate_0036

Transparent asset:
  decision = allow
  assetPath = assets/transparent/m29_transparent_asset_candidate_0084.png
  analysisBbox = [533, 532, 71, 67]
  edgeAlphaMean = 0.0
  edgeAlphaCoverageGt32 = 0.0

Evidence contract:
  mode = allow_visible_replay
  promotionAllowed = true

Promotion:
  promoted object = m292_promoted_internal_icon_0005
  bbox = [533, 532, 71, 67]

M29.5:
  finalReplayAction = icon_replay
```

## Prevention Notes

同类问题应优先检查：

```text
OCR anchor 是否存在
M29.6 是否有多个同 anchor 相邻 fragments
transparent gate 是否拒绝单碎片但允许 union bbox
evidence contract 是否要求 transparent asset allow
promotion 是否只消费 allow_visible_replay
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
```
