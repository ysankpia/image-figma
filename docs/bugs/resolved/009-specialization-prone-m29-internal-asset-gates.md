# Bug: M29 internal asset chain 存在特化倾向的证据门控

- 状态：resolved
- 创建日期：2026-05-25
- 影响范围：M29.6 media internal decomposition、transparent asset report、internal source promotion、M29 contract docs/tests

## Summary

M29.6 内部资产分解已经避免了文案、文件名、行业、主题色、固定 bbox 这类硬特化；当前生产代码搜索也没有确认到这类 active literal/fixed-sample 特化规则。

这条链路仍有两类需要继续观察的结构性特化风险：

1. **OCR-anchor evidence bias**：内部 foreground pixel scanning 目前主要来自 raw M29 primitive 与 OCR 附近多方向窗口。它已经不是“只看文字上方”，但仍可能漏掉没有 OCR 锚点的内部图形、装饰对象、table marker、圆点或小图标。
2. **confidence gate drift**：当前实现已允许 `high` confidence 或 `groupSupportedExecution=true` 的 medium candidate 继续进入透明资产和 promotion gate，但文档、合同矩阵、reason 命名仍有 “high-confidence only” 的旧表述，容易把后续实现拉回单一置信度特化。

062 source-chain audit 和 Gemini 对照审计之后，本 bug 的跟踪范围扩大为以下通用 source-chain 缺陷：

1. **absolute pixel threshold drift**：M29.2、M29.6、transparent asset 和 selected marker 相关逻辑曾有多处绝对像素阈值。Stage 2 已引入内部 scale profile，并覆盖 M29.2 默认 options、M29.6 component/text mask/scan window、transparent preflight、selected tab indicator 的高风险尺寸 gate；后续仍需继续盘点 legacy/dead path 里的旧阈值。
2. **fixed candidate cap / scan budget**：M29.6 的 component/window candidate 提取曾存在固定 top-N 或固定窗口预算风险。Stage 2 已把 `[:6]` component 截断替换为基于窗口面积和 scale 的 return budget，并把 generic scan/candidate budget 改为 area-density aware；Stage 3 已给 selected marker / status dot / table marker 增加 M29.6 report-only 正向 role evidence；Stage 5 已把这些 marker role 接入 evidence contract / internal source promotion；Stage 6 已把 promotion exact bbox 去重改成 role-compatible spatial merge。后续仍需用真实 batch 验证实际覆盖面。
3. **transparent gate coupling**：Stage 4 已把 `analysisAllowed`、`assetGenerated`、`visibleReplayEligible`、`cleanupEligible` 拆开。alpha 分析和诊断 PNG 可以先产生，但只有 `visibleReplayEligible=true` 才能被 evidence contract / internal source promotion 当成可见回放证据；cleanup 仍固定由 M29.5 授权。
4. **promotion role narrowing**：Stage 5 已把 `selected_marker_candidate`、`table_marker_candidate`、`status_dot_candidate` 接入 `shape_geometry/shape_replay` source promotion。`internal_control_background` 仍只保留 role contract；在没有明确 M29.6 role/source evidence 前，不从普通内部图块硬造按钮背景。
5. **missing fate trace**：Stage 1 已加入 bridge fate trace report，用于聚合候选对象从 M29.6 到 final M29.5/materializer 的第一阻断层，避免后续修复退化成手动翻多个 report 后猜阈值。
6. **cleanup risk coupling**：Stage 7 已把 copied-image cleanup 风险门放回 final M29.5。高风险时只撤 copied-image cleanup target，并记录 `cleanup_rejected_*` risk；visible icon/shape replay 仍保留，materializer 仍只执行 M29.5 plan。
7. **single control-row execution gap**：064 已补上单个 media-contained control icon + OCR label 的通用 source-chain 路径。它不依赖品牌、文案、坐标或文件名；只依赖 directional OCR relation、低 text overlap、低 hero/texture risk、compact icon geometry 和 same-media containment。transparent alpha 失败时可以保留 visible source-crop replay，但 copied-image cleanup 仍必须由 final M29.5 风险门授权。
8. **full-raster ownership legacy trap**：065 将处理更深层根因。`preserve_raster / image_replay` 在复合 UI media 中仍近似独占整块像素，导致内部按钮、pill、badge、circle control 即使被发现，也只能作为父图上的 overlay，无法稳定夺回 pixel ownership。正确方向不是直接删除大图，也不是继续 full raster + overlay，而是 `residual_raster + proven_foreground_objects`。

这不是要删除数学阈值。面积、长宽比、foreground contrast、hero/texture penalty、text overlap、alpha coverage 这类阈值是正常数学参数；问题只出现在规则依赖单张样本、固定方向、固定文案、文件名、行业、主题色、固定 bbox，或把一个证据源当成唯一事实源。

## Reproduction

复现方式：

1. 上传真实图 `/Users/luhui/Library/Application Support/PixPin/Temp/PixPin_2026-05-25_14-43-04.png`，观察复合 media 区域内部的 action icon、未带 OCR 锚点的蓝色/圆形内部图形、以及底部 table 内小元素。
2. 查看最近上传任务 `backend/storage/upload_previews/task_4bcd6d4f5f7b` 的 M29.6 / transparent asset / promotion artifacts。
3. 旧行为中，只有部分 OCR 附近 icon 被提升，部分候选因 `internal_candidate_not_high_confidence` 被挡住，未被 OCR 锚定的内部 foreground 仍可能没有 source object。
4. 搜索 active backend code：
   - 未确认到按 `充值` / `提币` / `划转` / `买币`、文件名、行业、主题色、固定 bbox 的 active 特化。
   - 确认存在 OCR 多方向 anchor 窗口与 `high or groupSupportedExecution` gate。
5. 搜索 docs/contract：
   - `docs/architecture/backend.md`
   - `docs/engineering/current-mainline-code-map.md`
   - `docs/engineering/testing-strategy.md`
   - `docs/engineering/m29-contract-regression-matrix.md`
   仍有 high-confidence only 或类似旧表述，和当前 group-supported medium 逻辑不完全一致。

## Root Cause

根因是 evidence source 还不完整：

- M29.6 目前把 OCR anchor 当成最强的内部 UI foreground 证据。这对 icon-label row 有效，但不能覆盖所有内部图形资产。
- medium confidence 原本被当成不可执行，这在真实图上会把弱但有重复组支持的 icon 卡住。后续已引入 `groupSupportedExecution`，但合同和命名还没有完全跟上。
- 单个 control-row icon 即使有强 OCR 方向关系，也缺少独立 execution evidence；旧链路过度依赖 high confidence alpha asset 或 repeated group support，导致 “text 可编辑但旁边 icon/button 不可选”。
- 更深层的 full-raster ownership 假设仍在约束后续效果：父 media 先占有全部像素，后续 promoted internal object 只能争取 overlay 和局部 copied-image cleanup。对于轮播图、登录海报和 banner 这类复合 UI media，source truth 应该是 residual media owner 加 foreground claims，而不是父图永久独占所有内部 UI/control 像素。
- 没有独立的 anti-specialization regression guard 来阻止后续代码退化成“只看一个方向 / 只看一个文案 / 只看一个固定区域”的修补。

## Latest Evidence: task_8d5806b08f44

最新真实上传任务 `backend/storage/upload_previews/task_8d5806b08f44` 显示当前问题不是 pipeline 崩溃，而是 evidence -> asset -> promotion 的质量不足：

- pipeline 全部 stage completed；M29.6、transparent assets、promotion、final replay plan、materializer、visual comparison 都已产出。
- M29.6 生成 `229` 个 internal candidates，`140` 个 accepted report candidates，但 transparent asset 只允许 `10` 个，internal source promotion 只提升 `8` 个。
- transparent asset rejection 主因包括：
  - `internal_candidate_not_high_confidence`: `139`
  - `internal_candidate_not_accepted`: `54`
  - `overlaps_ocr_text`: `47`
  - `transparent_candidate_too_thin`: `29`
  - `unstable_background`: `34`
- 轮播区域四个 action icons 已能被提升，但 promoted icon PNG 仍可能包含局部深色背景/边缘残留；例如 `m292_promoted_internal_icon_0004.png` 的 edge alpha 仍偏高，说明 alpha mask 不是足够干净的 UI icon cutout。
- 当时 parent media cleanup 仍未解决：提升出来的 icon/text 是 overlay，父 media 内部原像素没有针对 promoted internal asset 做稳定擦除，所以视觉上可能仍有重复/残留/块感。第一轮修复已加入 M29.5 copied media cleanup 授权和 materializer alpha-mask 擦除；525 全量样本阶段仍需验证它是否足够稳定。
- table/card 内部小圆点、小图标、局部 marker 仍大量落在 `overlaps_internal_text_mask` 或 OCR-anchor 附近候选里；这证明 OCR anchor 不能继续作为主要入口，必须补 non-OCR internal foreground component 与 marker/circle evidence。

## Fix

已完成第一轮通用修复：

1. M29.6 内部候选来源已拆成多个证据源：
   - raw primitive inside media；
   - OCR-anchor local foreground；
   - non-OCR generic foreground component inside media。
2. OCR 现在只是 relation hint，不再是唯一 foreground 扫描入口。
3. Transparent asset extraction 新增 edge-alpha metrics 和 `edge_alpha_risk` 拒绝门，避免透明 PNG 周边仍带明显背景块。
4. Promotion permission 已明确为：

```text
PromoteInternalAsset(o) =
  accepted_report_candidate(o)
  and TransparentAssetAllowed(o)
  and (
    Confidence(o) = high
    or GroupSupportedExecution(o)
  )
  and not OwnershipConflict(o)
```

5. M29.5 会在 promoted internal asset 与 parent media 的 relation 成立且 cleanup risk gate 通过时写入 copied media cleanup 授权。
6. Materializer 只消费 M29.5 cleanup target，并优先用 transparent asset alpha mask 擦 parent copied media asset；如果 M29.5 因风险撤掉 copied-image cleanup target，materializer 仍必须创建对应 visible replay node。

064 追加修复：

1. M29.6 为单个 control-row internal icon 增加 `controlRowSupportedExecution`：
   - accepted internal icon；
   - directional OCR anchor；
   - low text overlap；
   - low hero/texture penalty；
   - compact icon-like geometry；
   - scale-aware size bounds；
   - same media/control containment。
2. Transparent asset report 保留 `controlRowSupportedExecution`，并在 alpha asset 因 edge/background 风险不可生成时，允许 `controlRowSourceCropEligible=true` 支撑 visible replay。
3. Evidence contract 允许 strong control-row relation evidence 替代 repeated group evidence，但仍必须通过 hard rejection、media containment、text overlap 和 hero risk gate。
4. Internal source promotion 对无 transparent asset path 的 source-crop fallback 使用原始 candidate bbox，不使用扩大的 analysis bbox；同时保留 matched OCR anchor id 到 `sourceEvidence.ocrBoxIds`。
5. M29.5 / ownership conservation 将 source-crop visible replay 和 transparent asset bbox-padding overlap 作为可解释可见重叠，但 copied-image cleanup 仍要求 transparent replacement 和 M29.5 cleanup target。

后续修复应继续按通用证据层推进：

1. 按 `docs/plans/completed/063-m29-source-chain-repair-and-anti-specialization-hardening.md` 新增 bridge fate trace report。
2. 增加 scale-aware threshold profile，优先处理高风险绝对像素阈值。已完成 Stage 2 第一轮：M29.2 / M29.6 / transparent / selected tab indicator 高风险 gate 已接入内部 scale profile。
3. 修复 M29.6 fixed top-N / fixed window cap 对小对象的漏检。已完成 Stage 2 第一轮：connected component 固定 top 6 截断已移除，generic scan/candidate budget 改为 scale-aware area-density budget。Stage 3 已补 selected marker / status dot / table marker 的 M29.6 report-only role evidence；后续需要在 evidence/promotion 层决定何时 replay as shape。
4. 拆分 transparent asset gate，允许 medium + strong independent evidence 的 candidate 进入 alpha analysis，但不绕过 evidence contract。已完成 Stage 4：diagnostic alpha asset 成功不再等同于 visible replay 权限，evidence contract / promotion / bridge fate trace 统一读取 `visibleReplayEligible`。
5. 增加 selected marker、table marker、status dot、internal control background 的正向 promotion role。已完成 Stage 5 的 marker/status/table 路径：shape role 不需要 transparent PNG，必须通过 evidence contract，再由 internal source promotion 写回 M29.2 `shape_geometry/shape_replay`；internal control background 继续等待明确 source role evidence。
6. 修复 promotion exact bbox dedupe。已完成 Stage 6：同角色高 IoU / 高 containment / 小幅 bbox 漂移合并为一个 promoted source，不同角色重叠记录 conflict，不静默覆盖。
7. 增加 cleanup risk gate。已完成 Stage 7：final M29.5 保留 visible replay，只在 alpha/text overlap/replacement style 等证据显示风险高时拒绝 copied-image cleanup target。
8. 继续增加 repeated small-object pattern、circular/marker primitive evidence、separator/control-background evidence。
9. 需要时再把 `RepetitionSupported(o)` 作为 promotion 许可来源，但必须先有独立 report/test 支撑。
10. 增加代码级/测试级 guard，禁止 literal text、filename、theme、industry、fixed bbox、single-direction-only anchor 进入 active mainline。
11. 执行 065 residual ownership rewrite：M29.6 提出 foreground claim，evidence contract 决定 `allow_foreground_claim`，internal source promotion 写回增强 M29.2，final M29.5 授权 residual copied-image cleanup，materializer 只执行 final plan。

## Regression Guard

已有保护：

- `test_media_internal_decomposition.py::test_ocr_anchor_foreground_uses_multiple_relations_not_only_above_text`
- `test_transparent_asset_report.py::test_group_supported_medium_internal_icon_uses_alpha_gate`
- `test_internal_source_promotion.py::test_internal_source_promotion_promotes_group_supported_medium_internal_icon`

已新增：

- 覆盖 non-OCR internal foreground component 的 report-only 候选测试。
- 更新 `docs/engineering/m29-contract-regression-matrix.md`，把 OCR-anchor、non-OCR foreground、group-supported medium 分开列为合同 case。
- 覆盖 transparent asset edge-alpha 风险拒绝。
- 覆盖 promoted internal asset 的 M29.5 copied media cleanup 授权和 materializer alpha-mask 擦除。
- 覆盖 ownership conservation 对 promoted internal icon copied-image cleanup 的解释；普通未提升 icon 仍不得擦 parent media。
- 覆盖 promotion IoU / containment dedupe，不因 1-2px bbox 漂移重复晋升。
- 覆盖 cleanup risk gate：promoted icon alpha/text 风险或 promoted shape replacement style 缺失时，M29.5 保留 visible replay 并只拒绝 copied-image cleanup。
- 覆盖 legacy import boundary：current mainline roots 不得重新 import pre-mainline M29 audit packages；OCR -> M29TextBox adapter 由 `app.ocr` 承担，legacy audit package 只保留兼容 re-export。

Stage 2 新增保护：

- `test_image_math_scale.py::test_scale_profile_uses_regular_ocr_height_and_records_basis`
- `test_image_math_scale.py::test_scale_profile_fallback_ignores_large_media_region_as_text_unit`
- `test_media_internal_decomposition.py::test_scaled_pixel_anchor_component_is_not_rejected_by_1x_area_cap`
- `test_media_internal_decomposition.py::test_many_small_non_ocr_components_are_not_limited_to_top_six`
- `test_transparent_asset_report.py::test_scaled_raster_icon_is_not_rejected_by_1x_area_cap`
- `test_source_ui_physical_graph.py::test_scaled_selected_tab_indicator_symbol_uses_ocr_scale_not_fixed_height`
- `test_media_internal_decomposition.py::test_selected_indicator_pixel_component_reports_marker_role_not_icon`
- `test_media_internal_decomposition.py::test_repeated_small_non_ocr_components_report_table_marker_role`

仍需新增：

- 覆盖 table/cell 内 circular marker 或 small icon 的通用 source evidence 测试。
- 覆盖 anti-specialization source scan 或 contract test：active M29 chain 不得出现 literal label、filename、industry、theme、fixed bbox 或 single-direction-only execution gate。
- 继续扩展 1x/2x/3x scale synthetic UI，用真实 batch 复核 table marker / status dot / selected marker 从 M29.6 role 到 promotion/replay as shape 的覆盖面。
- 覆盖 cleanup risk gate 的真实 artifact 指标：visible replay 成功但 copied-image cleanup 被拒绝时，B-stage/visual comparison 不应把它误诊断为 source promotion 失败。
- 覆盖 single control-row icon evidence：
  - `test_single_control_row_icon_text_geometry_supports_execution_without_repetition`
  - `test_large_hero_fragment_does_not_get_single_control_row_execution_support`
  - `test_control_row_internal_icon_is_execution_supported_without_group_support`
  - `test_control_row_internal_icon_with_edge_alpha_risk_allows_visible_source_crop_not_cleanup`
  - `test_control_row_supported_internal_icon_can_allow_visible_replay_without_alpha_asset`
  - `test_internal_source_promotion_promotes_control_row_source_crop_icon_without_transparent_asset`
  - `test_m295_keeps_control_row_source_crop_promoted_icon_without_copied_cleanup`
  - `test_control_row_source_crop_promoted_icon_overlap_is_explainable_without_copied_cleanup`
  - `test_control_row_source_crop_promoted_icon_cannot_claim_copied_cleanup_without_transparent_asset`
  - `test_promoted_internal_icon_transparent_padding_label_overlap_is_explainable_without_copied_cleanup`

## Validation Evidence

当前 bug 已进入 runtime 修复阶段；Stage 1-8 已改动内部报告、promotion、M29.5 cleanup 授权、legacy import boundary 和对应 tests/docs，但未改 public DSL/API/Renderer/plugin protocol。

已执行的相关验证：

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_internal_source_promotion.py -q
uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
git diff --check
```

最近通过结果：

```text
60 passed
```

最近验证命令：

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
```

063 Stage 2 验证：

```bash
cd backend
uv run pytest tests/test_image_math_scale.py tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_source_ui_physical_graph.py -q
uv run pytest tests/test_image_math_import_boundaries.py tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
```

结果：

```text
55 passed
93 passed
```

063 Stage 3 验证：

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py -q
uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py tests/test_upload_preview_pipeline.py -q
```

结果：

```text
17 passed
52 passed
```

063 Stage 4 验证：

```bash
python -m py_compile backend/app/transparent_asset_report/gates.py backend/app/transparent_asset_report/candidates.py backend/app/transparent_asset_report/pipeline.py backend/app/transparent_asset_report/report.py backend/app/m29_evidence_contract/scoring.py backend/app/internal_source_promotion/pipeline.py backend/app/m29_bridge_fate_trace/pipeline.py
cd backend
uv run pytest tests/test_transparent_asset_report.py tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py tests/test_m29_bridge_fate_trace.py -q
uv run pytest tests/test_transparent_asset_report.py tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
```

结果：

```text
34 passed
76 passed
```

063 Stage 5 验证：

```bash
python -m py_compile backend/app/m29_evidence_contract/scoring.py backend/app/m29_evidence_contract/pipeline.py backend/app/internal_source_promotion/pipeline.py backend/app/m29_bridge_fate_trace/pipeline.py backend/tests/test_m29_evidence_contract.py backend/tests/test_internal_source_promotion.py backend/tests/test_m29_bridge_fate_trace.py backend/tests/test_m29_replay_plan.py
cd backend
uv run pytest tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py tests/test_m29_bridge_fate_trace.py -q
uv run pytest tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py tests/test_m29_bridge_fate_trace.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
```

结果：

```text
25 passed
71 passed
```

063 Stage 6 验证：

```bash
python -m py_compile backend/app/internal_source_promotion/pipeline.py backend/tests/test_internal_source_promotion.py
cd backend
uv run pytest tests/test_internal_source_promotion.py -q
uv run pytest tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py tests/test_m29_bridge_fate_trace.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
git diff --check
```

结果：

```text
12 passed
74 passed
```

063 Stage 7 验证：

```bash
python -m py_compile backend/app/m29_replay_plan/cleanup.py backend/app/m29_replay_plan/pipeline.py backend/app/internal_source_promotion/pipeline.py backend/tests/test_m29_replay_plan.py
cd backend
uv run pytest tests/test_m29_replay_plan.py tests/test_internal_source_promotion.py -q
uv run pytest tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py tests/test_upload_preview_pipeline.py -q
```

结果：

```text
37 passed
66 passed
```

063 Stage 8 验证：

```bash
python -m py_compile backend/app/ocr.py backend/app/text_masked_media_audit/ocr_text.py backend/app/upload_preview/pipeline.py backend/app/source_ui_physical_graph/pipeline.py backend/app/plan_materializer/builder.py backend/tests/test_image_math_import_boundaries.py backend/tests/test_baidu_ocr.py backend/tests/test_text_masked_media_audit.py
cd backend
uv run pytest tests/test_image_math_import_boundaries.py tests/test_baidu_ocr.py tests/test_text_masked_media_audit.py -q
uv run pytest tests/test_upload_preview_pipeline.py tests/test_source_ui_physical_graph.py tests/test_m29_plan_materializer.py -q
```

结果：

```text
29 passed
48 passed
```

063 主验收集验证：

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/测试/images \
  --poll-timeout 300
```

结果：

```text
ledger: backend/tmp/validation/upload_preview_batch_20260526_184550/upload_preview_batch_validation.json
inputCount: 40
supportedCompletedTaskCount: 40
supportedFailedCount: 0
missingArtifactCount: 0
assetFetchFailedCount: 0
ownershipConflictTypeCounts: {}
totalVisibleOwnershipOverlapConflicts: 0
totalInternalCandidateCount: 1782
totalAcceptedInternalCandidateCount: 905
totalPromotedInternalSourceObjectCount: 86
totalBStageRepairCost: 244
averageDslVisualGateNormalizedMeanAbsError: 0.002257
maxDslVisualGateChangedPixelRatio10: 0.038229
```

064 focused validation:

```bash
cd backend
python -m py_compile \
  app/media_internal_decomposition/candidates.py \
  app/transparent_asset_report/candidates.py \
  app/transparent_asset_report/normalization.py \
  app/transparent_asset_report/pipeline.py \
  app/transparent_asset_report/gates.py \
  app/m29_evidence_contract/scoring.py \
  app/internal_source_promotion/pipeline.py \
  app/m29_replay_plan/overlap.py \
  app/ownership_conservation/conflicts.py

uv run pytest \
  tests/test_media_internal_decomposition.py \
  tests/test_transparent_asset_report.py \
  tests/test_m29_evidence_contract.py \
  tests/test_internal_source_promotion.py \
  tests/test_m29_replay_plan.py \
  tests/test_ownership_conservation.py \
  -q

uv run pytest \
  tests/test_m29_plan_materializer.py \
  tests/test_upload_preview_pipeline.py \
  tests/test_m29_bridge_fate_trace.py \
  -q
```

结果：

```text
py_compile passed
109 passed
27 passed
```

064 diagnostic image validation:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir tmp/validation/064_single_input \
  --output-dir tmp/validation/064_single_run \
  --poll-timeout 300
```

结果：

```text
inputCount: 1
supportedCompletedTaskCount: 1
supportedFailedCount: 0
missingArtifactCount: 0
assetFetchFailedCount: 0
totalVisibleOwnershipOverlapConflicts: 0
totalPromotedInternalSourceObjectCount: 11
```

关键 bridge fate trace：

```text
[176,1059,48,42] -> evidenceDecision=allow_visible_replay -> finalReplayDecision=icon_replay -> materializedNodeId=m29_symbol_0019
[156,1181,69,72] -> evidenceDecision=allow_visible_replay -> finalReplayDecision=icon_replay -> materializedNodeId=m29_symbol_0018
[155,1329,69,71] -> evidenceDecision=allow_visible_replay -> finalReplayDecision=icon_replay -> materializedNodeId=m29_symbol_0017
```

064 525 real-sample validation:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/525测试 \
  --output-dir tmp/validation/064_525_run_2 \
  --poll-timeout 300
```

结果：

```text
inputCount: 6
supportedCompletedTaskCount: 6
supportedFailedCount: 0
missingArtifactCount: 0
assetFetchFailedCount: 0
totalVisibleReplayClaimCount: 426
totalVisibleOwnershipOverlapConflicts: 0
totalPromotedInternalSourceObjectCount: 66
totalBStageRepairCost: 36
ownershipConflictTypeCounts: {}
```

525 批量验证第一轮修复：

```text
baseline ledger:
  backend/tmp/validation/upload_preview_batch_20260525_195912/upload_preview_batch_validation.json
  ownershipConflictTypeCounts = {"invalid_copied_image_asset_cleanup": 12}
  totalBStageRepairCost = 547

post-fix ledger:
  backend/tmp/validation/upload_preview_batch_20260525_200800/upload_preview_batch_validation.json
  ownershipConflictTypeCounts = {}
  totalBStageRepairCost = 403
```

## Prevention Notes

后续处理这类问题时，不允许：

- 按 `充值`、`提币`、`划转`、`买币` 等文案写规则。
- 按 PixPin 文件名、上传文件名、行业、App 类型、主题色写规则。
- 按固定 bbox、固定屏幕位置、固定轮播/表格样本写规则。
- 在 materializer、Renderer 或 Figma plugin 里补 source ownership。

允许：

- 增加通用 pixel/component evidence。
- 增加通用 relation graph evidence。
- 增加通用 repetition/group evidence。
- 增加可审计 report-only 阶段。
- 用真实图批量验证阈值，但阈值必须是可解释的数学参数，不得绑定某张图。
