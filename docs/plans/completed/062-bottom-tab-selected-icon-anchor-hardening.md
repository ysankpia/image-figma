# Bottom tab selected icon anchor hardening

- 状态：completed
- 创建日期：2026-05-26
- 完成日期：2026-05-26
- 负责人：Codex

## Goal

修复真实资产样本中底部 tab 的选中态 `资产` 图标没有成为独立 icon layer、选中横线被误当成 icon 的问题。

## Scope

包含：

- M29.6 media internal decomposition 的 OCR label anchor 归属扩展。
- M29.2 source ownership 对 selected tab indicator 横线的 icon 误分类抑制。
- 对应 regression tests、bug record、M29 contract regression matrix。
- 使用最新真实 task artifact 复验。

不包含：

- 不修改 DSL/API/Renderer/Figma plugin protocol。
- 不新增图像依赖。
- 不按文字、文件名、task id、固定坐标、主题色或单截图结构特化。
- 不放宽所有 `non_ocr_foreground` promotion gate。

## Steps

1. 记录真实 task 的失败链路：选中态 icon 为 M29.6 non-OCR foreground，选中横线进入 standalone icon。
2. 补测试覆盖 near-media OCR label anchor 和 selected indicator 非 icon。
3. 新增 evidence-aware soft-edge alpha profile，只允许强 OCR anchor + group support + 低 text overlap + 低 hero penalty 的内部 icon 使用。
4. 调整 evidence contract：`pixel_component/non_ocr_foreground` 只有在强锚点和 group support 下才能 visible replay。
5. 调整 M29.5 去重和 ownership conservation：promoted internal icon 与 parent media、低 overlap label、near-equal promoted candidates 的关系必须可解释且只保留最高 evidenceScore。
6. 跑 targeted/core M29 tests。
7. 复跑真实上传图，确认 selected tab icon replay，selected indicator 不再是 icon。

## Acceptance

- 底部 5 个 tab label 都保持 text replay。
- 底部 5 个 tab icon 都能成为独立 visible icon replay。
- 选中态横线不再作为 `standalone_symbol_icon / icon_replay`。
- M29.6 仍然只产生 evidence/report，不直接创建 visible nodes 或 cleanup 权限。
- Materializer/Renderer/plugin 不承担 source ownership 修复。

## Validation

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py tests/test_source_ui_physical_graph.py tests/test_transparent_asset_report.py tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
```

真实样本复验：

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py --input-dir <single-real-sample-dir> --poll-timeout 300
```

实际验证：

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py tests/test_source_ui_physical_graph.py tests/test_transparent_asset_report.py tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py tests/test_upload_preview_pipeline.py -q
```

结果：

```text
125 passed in 17.23s
```

真实样本复跑：

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /tmp/m29_bottom_tab_single --poll-timeout 300
```

结果：

```text
ledger = backend/tmp/validation/upload_preview_batch_20260526_141939/upload_preview_batch_validation.json
task = task_144694879ab0
completedTaskCount = 1
degradedRecordCount = 0
backendCrashCount = 0
totalVisibleOwnershipOverlapConflicts = 0
totalTransparentAssetAllowedCount = 24
totalPromotedInternalSourceObjectCount = 21
```

关键 artifact：

```text
Transparent asset:
  sourceObjectId = m292_object_0094:internal_candidate_0019
  decision = allow
  alphaProfile = anchored_soft_edge_icon
  edgeAlphaCoverageGt32 = 0.2633
  largestComponentRatio = 0.9491

M29.5:
  m292_promoted_internal_icon_0020 -> icon_replay
  copied_image_asset cleanup target -> m292_object_0094
  m292_object_0131 selected indicator -> diagnostic_only

Ownership conservation:
  conflictCount = 0
```

## Notes

第一性原理判断：

```text
source truth:
  source PNG pixels + raw M29 primitive/blocked evidence + OCR label bbox + M29.6 candidate evidence。

information-loss point:
  selected tab 的 icon、label、indicator 被当成散乱 foreground，而不是同一 tab item 内的不同角色。

owning layer:
  M29.6 candidate anchor attribution and M29.2 source ownership classifier。

do-not-do:
  不下游补图层，不按“资产”文案补，不放宽全局 confidence/transparent gate。
```
