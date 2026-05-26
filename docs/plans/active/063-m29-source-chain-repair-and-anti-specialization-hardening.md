# 063 M29 Source-Chain Repair And Anti-Specialization Hardening

- 状态：active
- 创建日期：2026-05-26
- 负责人：Codex

## Goal

把 062 source-chain audit 和 Gemini 对照审计转成可执行的分阶段修复。目标不是修某张图、某个文案、某个品牌图标或某个固定 bbox，而是修通当前 M29 主链中真实 UI 对象从 evidence/report surface 回到 source ownership 的通用路径。

第一性原理结论：

```text
当前主要问题不是 Renderer/Figma/plugin 画不出来；
而是 icon/button/tab marker/table marker/status dot 等对象
在 M29.6 -> transparent asset -> evidence contract -> internal source promotion -> final M29.5
之间被挡住，没有成为 final M29.2 source object。
```

本计划的最终目标：

```text
候选对象命运可追踪
绝对像素特化风险下降
internal candidate extraction 不因固定 cap 丢小对象
transparent asset gate 分离 analysis / visible replay / cleanup
promotion 支持 icon 之外的 marker/control-background/source roles
M29.5 仍是 visible replay 和 cleanup 的唯一授权层
materializer 仍是执行器，不发明 owner
```

## Source Inputs

正式审计输出：

```text
docs/code-reviews/m29-first-principles-source-chain-audit/
```

对照审计输入：

```text
docs/code-reviews-gemini/
```

当前 bug 入口：

```text
docs/bugs/open/009-specialization-prone-m29-internal-asset-gates.md
```

Gemini 对照报告中采纳的方向：

```text
scale-aware thresholds
IoU / containment based promotion dedupe
shrink-edge / inner-edge sampling for tiny edge-touching assets
absolute-pixel-threshold audit
```

Gemini 对照报告中不作为主线采纳的方向：

```text
performance-first connected component rewrite before source-chain correctness
materializer directly consuming transparent_asset_report to create missing nodes
blanket removal of unanchored generic foreground rejection
visual diff score as source truth
single task / single Google icon / single bbox acceptance
```

## Scope

包含：

- 新增 bridge fate trace report，聚合 internal candidate 从 M29.6 到 materializer 的最终命运。
- 引入内部 scale profile，逐步把高风险绝对像素阈值改成基于源图证据的 scale-aware 参数。
- 重构 M29.6 candidate extraction，消除固定 top-N component cap 对小对象的漏检。
- 拆分 transparent asset gate：analysis allowed、asset generated、visible replay eligible、cleanup eligible。
- 扩展 evidence contract / promotion role，使 selected marker、table marker、status dot、internal control background 能回到 M29.2 source object。
- 用 IoU / containment 合并 promoted candidate，避免 1-2px 偏移重复晋升。
- 增加 cleanup/render-back risk gate，防止双影、破洞、脏边。
- 最后盘点 legacy/dead path，先标记再删除。

不包含：

- 不改 public DSL schema。
- 不改 `POST /api/upload-preview` 或 `GET /api/tasks/{taskId}/dsl` 的 public contract。
- 不改 Renderer / Figma plugin protocol。
- 不恢复 M29 Direct、legacy M30、M31-M39/M39.1、ONNX proposer。
- 不按文字、品牌、文件名、task id、路径、主题色、固定坐标、固定 bbox、单张截图结构写规则。
- 不让 materializer、Renderer 或 plugin 发明 source ownership、cleanup permission 或 missing node。

## Stages

### Stage 0: Audit Contract And Bug Ledger

状态：completed，提交 `3c5d21b docs: record m29 source-chain hardening plan`。

落本计划，提交 062 audit reports、Gemini 对照目录、bug 009 更新和 docs index 更新。

验收：

```text
文档能回答 Google/button/tab/table marker 为什么出不来。
明确 Gemini 建议哪些采纳、拒绝、延后。
明确 source-chain 修复边界，而不是下游补丁。
```

### Stage 1: Bridge Fate Trace Report

状态：completed，提交 `6319a88 feat: add m29 bridge fate trace report`。

新增只读报告：

```text
m29_bridge_fate_trace/bridge_fate_trace_report.json
```

每个 internal candidate 至少记录：

```text
candidateId
candidateRole
sourceObjectId / parentMediaSourceObjectId
bbox
transparentDecision
evidenceDecision
promotionDecision
finalReplayDecision
materializerDecision
firstBlockingStage
firstBlockingReason
evidenceScore
```

验收：

```text
对 task_33428579a6f7 一类 artifact，可以直接看到第一阻断层。
Stage 1 不改变 runtime 行为。
```

### Stage 2: Scale Normalization

状态：completed，提交 `526bc73 feat: add scale-aware m29 internal asset gates`。

新增内部 scale profile：

```text
textUnitPx = median regular OCR text height
fallbackUnitPx = function(image width, image height, source object distribution)
scaleBasis = robust(textUnitPx, fallbackUnitPx)
```

优先改高风险绝对像素阈值：

```text
M29.2 source_ui_physical_graph options
M29.6 component area / short edge / scan window
selected marker / tab indicator size gates
text mask padding
transparent tiny object edge sampling window
```

Stage 2 实现边界：

```text
内部 scale profile 写入 M29.2 / M29.6 / transparent report meta；
M29.6 text mask padding、component 面积/短边、generic scan window 和 component return budget 走 scale-aware 参数；
transparent asset candidate preflight 的面积/短边 gate 走 scale-aware 参数；
M29.2 默认 source_ui_physical_graph options 从图像 fallback scale 派生，避免待判断的大 OCR display text 反过来抬高自己的 preserve 阈值；
selected tab indicator 的局部几何 gate 使用 OCR text height 进行尺度归一化。
```

Stage 2 不改变：

```text
public API / DSL / Renderer / plugin protocol；
M29.6 / transparent report-only 合同；
internal source promotion role；
M29.5 visible replay / cleanup 授权边界。
```

Stage 2 验证：

```bash
cd backend
uv run pytest tests/test_image_math_scale.py tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_source_ui_physical_graph.py -q
uv run pytest tests/test_image_math_import_boundaries.py tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
```

保留合理比例阈值：

```text
overlap ratio
containment ratio
aspect ratio
coverage
text overlap
hero penalty
cleanup risk
```

### Stage 3: M29.6 Candidate Extraction Correctness

状态：completed，提交 `3f805f7 feat: add m29 internal marker candidate roles`。

修复 candidate extraction 的固定 cap 和固定窗口问题：

```text
移除或替换 connected components 只返回 top 6 的固定截断
generic scan window 改成 scale-aware/adaptive
candidate cap 改成基于区域面积、对象密度、OCR anchor/repetition 的风险预算
小 marker/status dot/table marker 不被大块 foreground 挤掉
```

Stage 3 实现边界：

```text
M29.6 pixel candidate role 从单一 internal_icon_candidate 扩展为 report-only marker roles：
  selected_marker_candidate
  status_dot_candidate
  table_marker_candidate

selected marker thin component 只在 below_text anchor window 中允许进入 component extraction；
非 marker 的长条 foreground 仍按 separator/long-thin 风险拒绝；
repeated small marker geometry 只改变 M29.6 report role/reasons，不进入 transparent/evidence/promotion visible replay。
```

Stage 3 不改变：

```text
transparent asset candidate source selection；
evidence contract allow_visible_replay 规则；
internal source promotion；
M29.5 replay / cleanup；
materializer / Renderer / plugin。
```

Stage 3 验证：

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py -q
uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py tests/test_upload_preview_pipeline.py -q
```

### Stage 4: Transparent Asset Gate Split

状态：completed，提交 `deb9414 feat: split transparent asset replay gates`。

拆分当前透明资产硬门：

```text
analysisAllowed
assetGenerated
visibleReplayEligible
cleanupEligible
```

允许 medium + strong independent evidence 的 candidate 进入 alpha analysis，但仍必须通过 evidence contract 和 promotion 才能 visible replay。cleanup 仍只能由 M29.5 授权。

Stage 4 实现边界：

```text
transparent asset report 继续保持 report-only，可生成 diagnostic alpha asset；
diagnostic alpha asset 成功不再等同于 visible replay 权限；
evidence contract / internal source promotion / bridge fate trace 统一读取 visibleReplayEligible；
旧报告缺少 visibleReplayEligible 时保持 decision=allow + assetPath 的兼容 fallback；
cleanupEligible 固定为 false，并记录 M29.5 replay plan 才能授权 cleanup。
```

Stage 4 不改变：

```text
public API / DSL / Renderer / plugin protocol；
M29.6 candidate role；
internal source promotion role；
M29.5 replay / cleanup；
materializer / Renderer / plugin。
```

Stage 4 验证：

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

### Stage 5: Evidence Contract And Promotion Role Expansion

状态：completed，已提交 `540d063 feat: promote internal marker roles as shapes`。

promotion 从 internal icon 单一路径扩展为多角色 source promotion：

```text
internal_icon_candidate -> raster_icon / icon_replay
internal_control_background -> shape_geometry / shape_replay
selected_marker -> shape_geometry / shape_replay
table_marker -> shape_geometry / shape_replay
status_dot / indicator_shape -> shape_geometry / shape_replay
```

不新增 public DSL 类型；通过 existing source object kind、replay decision 和 `sourceEvidence.role` 表达内部语义。

Stage 5 实现边界：

```text
internal_icon_candidate 仍走 raster_icon / icon_replay，且仍要求 transparent visibleReplayEligible=true；
selected_marker_candidate / table_marker_candidate / status_dot_candidate 走 shape_geometry / shape_replay；
shape role 不要求 transparent PNG，style 由 source pixels / promoted sourceEvidence 进入现有 shape materialization；
bridge fate trace 对 shape candidate 不再误报 missing transparent asset；
internal_control_background 只保留 role contract，不从普通内部图块硬造按钮背景。
```

Stage 5 不改变：

```text
public API / DSL / Renderer / plugin protocol；
materializer visible-node source truth；
M29.5 replay / cleanup 授权边界；
transparent asset report 对 marker/status/table 的 report-only 边界；
promotion exact bbox dedupe 仍留给 Stage 6。
```

Stage 5 验证：

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

### Stage 6: Promotion Dedupe And Overlap Merge

状态：completed，已提交 `2a1d1bf feat: merge promoted internal source overlaps`。

把 exact bbox dedupe 改成 IoU / containment based merge。相同角色高度重叠合并，不同角色冲突进入 report/reject，不做静默覆盖。

Stage 6 实现边界：

```text
promotion dedupe 从 exact bbox key 改成 spatial overlap merge；
same promotion role 高 IoU / 高 containment / 小中心漂移 + 小尺寸漂移时只保留 evidence rank 更高的 candidate；
不同 role 高重叠时记录 conflicting_promoted_internal_role_overlap，不静默覆盖；
相邻但不重叠的小 marker/status/table object 保持多个 promoted source objects；
dedupe 仍发生在 internal_source_promotion，不下沉到 materializer/Renderer/plugin。
```

Stage 6 验证：

```bash
python -m py_compile backend/app/internal_source_promotion/pipeline.py backend/tests/test_internal_source_promotion.py
cd backend
uv run pytest tests/test_internal_source_promotion.py -q
```

结果：

```text
12 passed
```

### Stage 7: Cleanup And Render-Back Risk Gate

状态：completed，提交待创建。

cleanup 风险检查只用于防止错误擦除，不作为 source truth：

```text
local before/after patch visual error
alpha mask coverage sanity
double-owned area
unexplained erased area
cleanup target has replacement owner
```

visible replay 安全但 cleanup 风险高时，允许 visible replay，拒绝 cleanup。

Stage 7 实现边界：

```text
cleanup risk gate 位于 final M29.5 replay plan；
M29.5 继续创建 visible replay plan item；
高风险时只撤 copied_image_asset cleanup target，不撤 icon_replay / shape_replay；
materializer 只执行 M29.5 cleanupTargets，不重新判断 cleanup safety；
promoted internal icon cleanup 使用 transparent alpha metrics、text overlap 和 parent media relation；
promoted table/status shape cleanup 要求 replacement style evidence，缺失时保留 shape replay 并拒绝 copied-image cleanup。
```

Stage 7 不改变：

```text
public API / DSL / Renderer / plugin protocol；
M29.6 / transparent / evidence contract 的 report-only 边界；
internal source promotion source truth 边界；
materializer 执行器职责；
B-stage quality / visual comparison 的诊断职责。
```

Stage 7 验证：

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

### Stage 8: Legacy / Dead Path Cleanup

先做 import/test inventory，标记 active、compat-only、dead-path debt，再单独删除。不得仅凭历史文档或 Gemini 结论删除。

## Acceptance

- Bridge fate trace 能解释关键 candidate 的第一阻断层。
- Google/button/icon 类 media-contained 对象有 source promotion 路径。
- bottom tab selected marker 有 shape replay 路径，不再被误当 icon 或完全丢失。
- table/status marker 有 shape replay 路径。
- 文字可编辑但图标/按钮/marker 不可选的断点明显减少。
- 没有 literal text、brand、filename、task id、fixed bbox、fixed coordinate、theme color 特化。
- materializer/Renderer/plugin 没有下游补 source ownership 的逻辑。
- 40 图主验收集无系统性回退。

## Validation

Stage 级 focused tests：

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py -q
uv run pytest tests/test_transparent_asset_report.py -q
uv run pytest tests/test_m29_evidence_contract.py -q
uv run pytest tests/test_internal_source_promotion.py -q
uv run pytest tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py -q
```

主真实样本验证：

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/测试/images \
  --poll-timeout 300
```

525 回归集：

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/525测试 \
  --poll-timeout 300
```

收口检查：

```bash
git diff --check
git status --short --branch
```

## Notes

`numpy` 和 `scikit-image` 已在 backend 依赖中；后续如使用它们做 connected components，不算新增依赖。但性能优化不能排在 source-chain correctness 前面。

所有阶段都要保留当前主线边界：

```text
M29.6 / transparent asset / evidence contract = evidence/report surfaces
internal source promotion = bridge back to M29.2
final M29.5 = visible replay and cleanup authorization
materializer = executor only
```
