# Current Mainline Code Map

本文档只描述当前代码职责和阅读顺序，作为后续拆分长文件的依据。它不引入新 runtime stage、不改变 API、不替代架构文档。

当前事实链：

```text
Plugin upload
-> backend/app/upload_preview/
-> OCR
-> raw M29 primitive graph
-> M29.2 ownership
-> M29.3 relation
-> M29.4 weak cluster
-> M29.5 replay plan
-> M29 ownership conservation report
-> M29.6 media internal decomposition report
-> M29 transparent asset report
-> M29 evidence contract report
-> M29 internal source promotion
-> final M29.3/M29.4/M29.5 reports from promoted M29.2
-> M29 hierarchy candidate report
-> M29 sibling group candidate report
-> M29 layout energy report
-> M29 Auto Layout permission report
-> M29 plan-driven materializer
-> M29 bridge fate trace report
-> M29 design token report
-> M29 B-stage quality report
-> DSL v0.1
-> Renderer
```

M29 Direct compare, legacy M30 materialization, M31-M39/M39.1 downstream experiments, and ONNX proposer have been pruned from active backend runtime.

## Runtime Entry Surface

`backend/app/main.py` 装配当前 route modules：

```text
backend/app/routes/health.py
backend/app/routes/upload_preview.py
backend/app/routes/tasks.py
backend/app/routes/assets.py
```

当前产品上传入口是 `POST /api/upload-preview`。旧 `POST /api/upload`、`GET /api/tasks/{taskId}/m29-direct-dsl`、`GET /api/tasks/{taskId}/m30-materialization`、旧 M8-M28 debug endpoints，以及 M31/M39/M39.1 diagnostic endpoints 已从 active runtime 移除；不要在新工作里恢复它们。

## Pipeline Orchestrator

`backend/app/upload_preview/` 是当前后端主编排 package。它负责：

```text
validate upload
save source PNG
run OCR
run M29/M29.2/M29.3/M29.4/M29.5
run M29 ownership conservation report
run M29.6 media internal decomposition report
run M29 transparent asset report
run M29 evidence contract report
run M29 internal source promotion
rerun M29.3/M29.4/M29.5/ownership from promoted M29.2
run M29 hierarchy candidate report
run M29 sibling group candidate report
run M29 layout energy report
run M29 Auto Layout permission report
run M29 plan-driven materialization
run M29 bridge fate trace report
run M29 design token report
run M29 B-stage quality report
publish M29 assets
write task status and stage timings
```

模块边界：

```text
pipeline.py: upload preview 主编排顺序
types.py: pipeline error/profile/artifact policy 类型
paths.py: upload preview storage path layout
timings.py: stage timing record/write logic
task_state.py: task status/error/completion writes
stages.py: OCR/M29/M29.2/M29.3/M29.4/M29.5/ownership-conservation/media-internal-decomposition/transparent-asset/evidence-contract/internal-source-promotion/hierarchy-candidate/sibling-group/layout-energy/auto-layout-permission/materialization/bridge-fate-trace/design-token/B-stage-quality stage wrappers
assets.py: M29 materialized assets publish
```

这些模块不承载 owner、relation、cleanup 授权或 materialization 策略。

OCR document to M29 text-box conversion is owned by `backend/app/ocr.py` via `text_boxes_from_ocr_document`. Current mainline packages must import that adapter from `app.ocr`, not from historical M29 audit packages.

## Source Truth Layer

### Raw M29 Primitive Graph

Raw M29 的领域实现已拆到 `backend/app/visual_primitive/`：

```text
types.py: raw M29 dataclasses and Literal contracts
bbox.py: bbox math and bbox set operations
mask.py: binary mask construction, overlap, validation, PNG export
metrics.py: region metrics, color distance, numeric clamps
pixels.py: pixel crop, region/ring sampling, debug rectangle drawing
geometry.py: shape geometry fit, support occupancy fit, radius/layer hint helpers
components.py: text exclusion mask, foreground mask, connected components, image protection mask
detectors.py: text/shape/image/symbol/blocked primitive detector logic
support.py: low-contrast and text-support background detector orchestration
support_scoring.py: support bbox search, scoring, and boundary delta helpers
relations.py: containment relation construction and stable source ordering
artifacts.py: node asset export, overlays, preview sheet helpers
validation.py: M29 document, blocked context, artifact validation, and meta
```

`backend/app/visual_primitive_graph.py` 仍是兼容入口和 thin orchestration 文件，继续导出 `extract_m29_visual_primitive_graph` 以及历史调用方依赖的 M29 类型和函数。它负责：

```text
source PNG read/decode
stage ordering across text, foreground, component, detector, relation, asset, debug, validation steps
final nodes.json write
```

拆分不能改变 primitive IDs、metrics、geometry contract、support detector gates、asset paths 或 output JSON shape。

### M29.2 Ownership

`backend/app/source_ui_physical_graph/` 负责把 raw M29/OCR/source pixels 转成 source objects：

```text
visualKind
pixelOwner
replayDecision
source lineage
physical metrics
```

这是 source ownership gate。修文字支撑背景、深色 UI raster/media 丢失、复杂头像/图表/照片被误画成 shape 等问题时，应从 raw M29 detector 或 M29.2 owner contract 修起，不能在 materializer/Renderer/plugin 按文字内容、颜色或主题伪造。

M29.2 当前也负责把有物理证据的大型复杂 image-like unknown 恢复为 `media_region` / `preserve_raster` / `image_replay`，为 fallback-off 场景提供 raster/media preservation。

M29.2 默认 options 会从源图自身推导内部 scale profile。该 profile 只用于把高风险绝对像素 gate 归一到当前截图尺度，例如 icon area、cluster gap、control-like unknown size、media/display-text size。它不是设备型号、文件名、Retina 倍率或样本路径规则；display-text 的 preserve 判断使用图像 fallback scale，避免待判断的大 OCR 文字反过来抬高自己的阈值。局部 selected tab indicator 几何判断可以使用 OCR text height 做尺度归一，但仍输出 diagnostic/non-icon，除非后续 source role evidence 另行证明它应该 replay as shape。

模块边界：

```text
pipeline.py: M29.2 extraction orchestration and JSON write
types.py: M29.2 source object/options/type contracts
media.py: media/image-like source object classification
text.py: OCR text editability and preserve-raster text classification
icons.py: symbol fragment cluster to raster icon ownership
shapes.py: shape replay safety and foreground-shape routing
unknowns.py: diagnostic unknown routing
blocked.py: recoverable blocked foreground routing
dedupe.py: source object priority dedupe and stable rename
artifacts.py: summary, overlay, bbox parsing, local background confidence
```

### M29.3 Relation

`backend/app/region_relation_kernel.py` 是纯 bbox/geometry kernel，定义：

```text
near_equal
contains
contained_by
overlaps
disjoint
near
direction
alignment
size similarity
```

`backend/app/region_relation_graph_report.py` 把 M29.2 source objects 两两关系写成 report。下游不应再临时实现另一套 contains/near/duplicate 判断。

### M29.4 Weak Cluster

`backend/app/stable_design_cluster/` 从 relation graph 产出 weak structural evidence：

```text
row_like
column_like
background_anchor_like
repeated_item_like
```

这些 cluster 是 report-only evidence，不给组件化、Auto Layout、Figma Component/Instance 或 materialization 权限。

模块边界：

```text
pipeline.py: M29.4 report orchestration and JSON write
types.py: options/result and relation/cluster Literal contracts
normalization.py: M29.3 relation graph node/edge normalization
candidates.py: motif connected-component candidate generation
motifs.py: edge motif classification and weak role hints
clusters.py: cluster acceptance, dedupe, stable IDs
scoring.py: stability/repeatability/risk scoring helpers
report.py: summary construction
validation.py: report schema and read-only invariant checks
geometry.py: bbox/member overlap and deterministic sort helpers
```

### M29.5 Replay Plan

`backend/app/m29_replay_plan/` 是正式 materialization 前的质量门。它负责：

```text
map M29.2 replay decisions to final plan actions
dedupe near-equal owners
sort visible replay order
enforce node budget
authorize fallback cleanup
authorize copied image asset cleanup
gate copied image asset cleanup risk without cancelling visible replay
apply visible ownership overlap suppression
record risk and cluster support
```

M29.5 只写 plan，不创建 DSL visible nodes。Plan target roles are:

```text
m29_text
m29_shape
m29_image
m29_symbol
```

模块边界：

```text
pipeline.py: M29.5 replay plan orchestration and JSON write
types.py: options/result and replay action/target role Literal contracts
normalization.py: M29.2 source object normalization
lookups.py: M29.3 edge and M29.4 cluster lookup construction
decisions.py: replay action mapping, target role, duplicate priority
cleanup.py: fallback and copied-image asset cleanup authorization/risk gating
overlap.py: visible replay overlap suppression for duplicate media, text, icon, and shape owners
budget.py: visible node budget suppression and duplicate plan items
report.py: reasons and summary construction
validation.py: report schema and read-only invariant checks
utils.py: stable sort and ordered dedupe helpers
```

### M29 Ownership Conservation

`backend/app/ownership_conservation/` 是 M29.5 之后、materialization 之前的全局 ownership conservation report。它消费：

```text
M29.2 source objects
M29.3.1 relation graph
M29.5 replay plan
```

它创建：

```text
storage/upload_previews/{taskId}/m29_ownership_conservation/ownership_conservation_report.json
```

模块边界：

```text
pipeline.py: report extraction orchestration and JSON write
types.py: visible/non-visible action constants and result type
normalization.py: M29.2 source object and M29.5 plan item normalization
relations.py: M29.3 edge lookup and media/text relation checks
geometry.py: bbox overlap, intersection, union, and ratio helpers
claims.py: source object, visible replay, and cleanup claim construction
conflicts.py: conservation conflict and warning detection
report.py: summary counts and read-only invariant fields
validation.py: report schema and report-only invariant checks
```

这个 package 只报告风险，不改变任何输入对象。它不创建 DSL nodes，不改 M29.5 plan，不授权 cleanup，不被 materializer 消费。

### M29.6 Media Internal Decomposition

`backend/app/media_internal_decomposition/` 是 ownership conservation 之后、materialization 之前的 report-only composite-media evidence surface。它消费：

```text
OCR blocks
source PNG pixels
raw M29 primitive nodes and blocked evidence
M29.2 source objects
M29.3.1 relation graph metadata
M29.5 replay plan metadata
```

它创建：

```text
storage/upload_previews/{taskId}/m29_media_internal_decomposition/media_internal_decomposition_report.json
```

模块边界：

```text
pipeline.py: report extraction orchestration and JSON write
types.py: report-only constants and result type
normalization.py: OCR/raw M29/M29.2/M29.5 normalization
geometry.py: bbox containment, overlap, padding, row/gap scoring helpers
candidates.py: composite media detection, text masks, OCR-anchor and non-OCR foreground component detection, internal candidate scoring, action-row grouping, rejection summaries
report.py: summary counts and report-only invariant fields
validation.py: report schema and report-only invariant checks
```

这个 package 只报告 `preserve_raster` media 内部 OCR/text-mask/raw symbol/shape/unknown candidate evidence，以及非 OCR internal foreground component evidence。OCR anchor 是 relation hint，不是唯一 foreground 扫描入口。Pixel candidates 可以携带 report-only roles，例如 `internal_icon_candidate`、`selected_marker_candidate`、`status_dot_candidate`、`table_marker_candidate`。这些 role 只是 source-chain 证据；M29.6 本身不创建 DSL nodes，不改 M29.5 plan，不生成透明资产，不提升 source ownership，不授权 cleanup，不被 materializer 消费。内部 icon 必须继续经过 transparent asset、evidence contract、internal source promotion 和 final M29.5；内部 marker/status/table shape role 不要求 transparent PNG，但仍必须经过 evidence contract、internal source promotion 写回 M29.2，并由 final M29.5 授权 visible replay。

M29.6 report meta 记录 `scaleProfile`。Text mask padding、pixel component min/max area、short-edge gate、generic scan window size、generic candidate budget、connected component return budget 都使用该内部 scale profile 或面积密度预算。比例证据仍保持比例形式：overlap ratio、containment ratio、aspect ratio、coverage、text overlap、hero penalty 和 cleanup risk 不应被改成固定样本规则。

### M29 Transparent Asset Report

`backend/app/transparent_asset_report/` 是 M29.6 之后、materialization 之前的 report-only transparent asset evidence surface。它消费：

```text
source PNG pixels
OCR blocks
M29.2 source objects
M29.6 media internal decomposition report
```

它创建：

```text
storage/upload_previews/{taskId}/m29_transparent_assets/transparent_asset_report.json
```

模块边界：

```text
pipeline.py: report extraction orchestration, diagnostic RGBA write, and JSON write
types.py: report-only constants and result type
normalization.py: OCR/M29.2/M29.6 normalization
geometry.py: bbox/image-bound and overlap helpers
candidates.py: allowed candidate-source selection and preflight gates
alpha.py: edge/context background sampling, dominant background cluster, alpha mask metrics, edge-alpha risk gate, and diagnostic RGBA output
gates.py: shared visible replay eligibility helpers for evidence/promotion/trace consumers
report.py: summary counts and report-only invariant fields
validation.py: report schema and report-only invariant checks
```

这个 package 只对已存在的 `raster_icon/icon_replay` source object 与 M29.6 `internal_icon_candidate` 做透明资产候选诊断。M29.6 internal candidate 必须是 accepted，且为 high confidence、有结构支持的 medium confidence，或具备强独立证据的 medium candidate 才能进入 alpha analysis；内部 media 候选使用 parent-media-clamped `analysisBbox` 做上下文 alpha 分析，避免 tight foreground bbox 的边缘采样把主体误当背景。alpha gate 会拒绝 unstable background、weak foreground、fragmented foreground、text overlap、thin geometry 和 edge-alpha background residue。它不扫描所有 media，不做通用人像/商品抠图，不替换 materialized assets，不提升 source ownership，不授权 cleanup，不被 materializer 直接消费。

Transparent asset report 明确拆分四个 gate：

```text
analysisAllowed: 是否允许进入 alpha/background analysis
assetGenerated: 是否实际生成 diagnostic RGBA asset
visibleReplayEligible: 是否允许作为 evidence contract / promotion 的可见回放证据
cleanupEligible: 永远 false；cleanup 只能由 final M29.5 replay plan 授权
```

`decision=allow` 和 `assetPath` 只表示诊断 alpha asset 生成成功；新代码必须优先读取 `visibleReplayEligible`，旧报告缺少该字段时才回退到 legacy `decision=allow + assetPath` 语义。

Transparent asset report meta 记录 `scaleProfile`。Preflight 的 candidate area 和 short-edge gate 使用同一内部 scale profile，避免高倍率 UI icon 因 1x 面积/短边上限被误拒。Alpha 背景稳定性、edge-alpha、foreground coverage 和 connected-foreground 仍是像素质量 gate，不因为 scale 成功就授权 visible replay 或 cleanup。

### M29 Evidence Contract

`backend/app/m29_evidence_contract/` 是 M29.6/transparent evidence 与 internal source promotion 之间的 report-only 证据合同层。它消费：

```text
M29.2 source objects
M29.6 media internal decomposition report
M29 transparent asset report
```

它创建：

```text
storage/upload_previews/{taskId}/m29_evidence_contract/evidence_contract_report.json
```

模块边界：

```text
pipeline.py: evidence contract report orchestration and JSON write
types.py: report-only constants and result type
scoring.py: positive/negative evidence scoring, risk gate, and decision construction
report.py: summary counts and report-only invariant fields
validation.py: report schema and report-only invariant checks
```

这个 package 把 internal UI icon 候选的 source score、size/compactness、text-anchor relation、same-media containment、repetition、transparent visible replay eligibility、text-overlap penalty、hero/texture penalty、cleanup risk 和 repair-cost penalty 合成 `allow_visible_replay` / `report_only` / `reject`。它也把 M29.6 明确标注的 shape role，例如 `selected_marker_candidate`、`status_dot_candidate`、`table_marker_candidate`，用 role support、compactness、repetition、same-media containment、text-overlap 和 hero/texture penalty 合成 shape replay 合同；shape role 不要求 transparent PNG。Generic `pixel_component/non_ocr_foreground` 只能作为 report/reject 证据，不能仅凭 alpha asset 生成成功直接 visible replay，避免地图路线、楼层线、下划线等媒体碎片被误升成图标或 shape。它不创建 source objects，不改 DSL，不改 assets，不授权 cleanup，不被 materializer 直接消费。`allow_visible_replay` 只允许 `internal_source_promotion` 把对应 M29.6 candidate 写回 promoted M29.2；之后仍必须重跑 M29.3/M29.4/M29.5。

### M29 Internal Source Promotion

`backend/app/internal_source_promotion/` 是 M29.6/transparent/evidence-contract evidence 回到 M29.2 source ownership 的唯一当前桥。它消费：

```text
M29.2 source objects
M29.6 media internal decomposition report
M29 transparent asset report
M29 evidence contract report
```

它创建：

```text
storage/upload_previews/{taskId}/m29_internal_source_promotion/internal_source_promotion_report.json
storage/upload_previews/{taskId}/m29_internal_source_promotion/source_ui_physical_graph.promoted.json
```

模块边界：

```text
pipeline.py: internal icon promotion and promoted M29.2 document write
types.py: promotion result and invariant metadata
```

这个 package 提升两类 M29.6 internal candidate。Icon path 仍只提升同时满足 M29.6 accepted `internal_icon_candidate`、transparent `visibleReplayEligible=true`，以及 evidence contract `allow_visible_replay` 的对象；若 transparent asset report 提供 `analysisBbox`，promotion 使用该 bbox 作为 promoted source bbox，并在 source evidence 中保留原始 `candidateBbox`，保证带上下文 padding 的透明 PNG 不会在 Figma 中被错误缩放。Shape path 只提升 evidence contract `allow_visible_replay` 的明确 shape role，例如 selected marker、table marker 和 status dot，写回 `shape_geometry` / `shape_replay` source object；shape path 不要求 transparent asset，也不把普通内部图块猜成按钮背景。Promotion dedupe 使用 IoU、containment、center shift 和 size drift 做 role-compatible spatial merge；同角色高重叠保留 evidence rank 更高者，不同角色高重叠记录 conflict，不静默覆盖。它不创建 DSL nodes，不绕过 M29.5，不再直接把 local confidence/alpha asset generation 当 promotion 权限。promotion 后 upload-preview 会用增强版 M29.2 重新生成 final M29.3.1、M29.4、M29.5 和 ownership conservation reports；M29.5 负责为 parent media relation 成立的 promoted internal asset 写 cleanup 授权，materializer 只消费 final M29.5 授权结果。

### M29 Bridge Fate Trace

`backend/app/m29_bridge_fate_trace/` 是 materialization 之后的 report-only diagnostic surface。它消费：

```text
M29.6 media internal decomposition report
M29 transparent asset report
M29 evidence contract report
M29 internal source promotion report
final M29.5 replay plan
M29 materialization report
```

它创建：

```text
storage/upload_previews/{taskId}/m29_bridge_fate_trace/bridge_fate_trace_report.json
```

模块边界：

```text
pipeline.py: joins candidate fate across M29.6/transparent/evidence/promotion/final replay/materialization
types.py: report-only constants and result type
report.py: summary counts by blocking stage/reason/role
validation.py: report schema and report-only invariant checks
```

这个 package 只解释 internal candidate 的命运：第一阻断层、阻断原因、transparent/evidence/promotion/final replay/materializer decision。Trace 会显示 `transparentVisibleReplayEligible` 和 `transparentGateDecision`，用于区分“诊断 alpha asset 已生成”和“可见回放证据已授权”。对 shape candidate，trace 会把 transparent decision 标记为 `not_required_for_shape_replay`，避免把 marker/status/table shape path 误诊断为缺失透明资产。它不创建 source objects，不改 M29.5 plan，不改 DSL，不改 assets，不授权 cleanup，不被 materializer 消费。它的目的是避免后续调阈值时手动翻多个 report。

### M29 Hierarchy Candidates

`backend/app/hierarchy_candidate_report/` 是 M29.5 之后、materialization 之前的 report-only hierarchy evidence surface。它消费：

```text
M29.2 source objects
M29.3.1 relation graph
M29.5 replay plan
```

它创建：

```text
storage/upload_previews/{taskId}/m29_hierarchy_candidates/hierarchy_candidate_report.json
```

模块边界：

```text
pipeline.py: report extraction orchestration and JSON write
types.py: visible/non-visible action constants and result type
normalization.py: M29.2 source object, M29.3 edge, and M29.5 plan item normalization
relations.py: relation lookup and child-in-parent metric helpers
geometry.py: bbox area, containment, oversize, and padding imbalance helpers
candidates.py: container candidate, parent candidate, and best-parent selection
report.py: summary counts and report-only invariant fields
validation.py: report schema and read-only invariant checks
```

这个 package 只报告候选父子结构，不改 replay plan，不直接创建 Group/Frame/Auto Layout。C-stage materializer 可以把它作为透明 controlled structure group 的证据来源，但不能借此重判 owner、改变 visible replay order 或创建 Auto Layout。

### M29 Sibling Group Candidates

`backend/app/sibling_group_candidate_report/` 是 M29.5 之后、materialization 之前的 report-only sibling-group evidence surface。它消费：

```text
M29.3.1 relation graph
M29.4 weak structural clusters
M29.5 replay plan
M29 hierarchy candidate report
```

它创建：

```text
storage/upload_previews/{taskId}/m29_sibling_groups/sibling_group_candidate_report.json
```

模块边界：

```text
pipeline.py: report extraction orchestration and JSON write
types.py: visible action constants, structural cluster role hints, and result type
normalization.py: M29.3 edge, M29.4 cluster, M29.5 plan item, and hierarchy selected-parent normalization
geometry.py: group bbox union and deterministic sort helpers
candidates.py: cluster-backed and relation-backed sibling group candidate construction
report.py: summary counts and report-only invariant fields
validation.py: report schema and read-only invariant checks
```

这个 package 只报告候选兄弟组，不改 replay plan，不直接创建 Group/Frame/Auto Layout。C-stage materializer 可以把高置信、低风险、root-level contiguous 的候选包成透明 controlled structure group。

### M29 Layout Energy

`backend/app/layout_energy_report/` 是 M29.5 之后、materialization 之前的 report-only layout evidence surface。它消费：

```text
M29.5 replay plan
M29 hierarchy candidate report
M29 sibling group candidate report
```

它创建：

```text
storage/upload_previews/{taskId}/m29_layout_energy/layout_energy_report.json
```

模块边界：

```text
pipeline.py: report extraction orchestration and JSON write
types.py: visible action constants, layout model constants, and result type
normalization.py: M29.5 plan item, sibling group, and hierarchy selected-parent normalization
subjects.py: sibling-group and hierarchy-children layout subject construction
geometry.py: bbox, gap, overlap, variance, and track helpers
energy.py: row/column/grid/overlay/absolute energy scoring
report.py: summary counts, internal-field stripping, and report-only invariant fields
validation.py: report schema and read-only invariant checks
```

这个 package 只报告候选 layout model 和 energy，不创建 Auto Layout，不改 replay plan。C-stage materializer 只可把它作为 group materialization 的附加准入证据；本阶段仍不创建真实 Auto Layout。

### M29 Auto Layout Permission

`backend/app/auto_layout_permission_report/` 是 M29 layout energy 之后、materialization 之前的 permission-only surface。它消费：

```text
M29 layout energy report
```

它创建：

```text
storage/upload_previews/{taskId}/m29_auto_layout_permission/auto_layout_permission_report.json
```

模块边界：

```text
pipeline.py: permission report extraction orchestration and JSON write
types.py: supported layout model constants, options, and result type
normalization.py: layout energy candidate normalization
permission.py: allow/defer/reject decision logic and recommended axis mapping
report.py: summary counts and permission-only invariant fields
validation.py: report schema and permission-only invariant checks
```

这个 package 只报告未来 Auto Layout 尝试许可，不创建 Auto Layout，不改 replay plan。C-stage materializer 可以消费 `allow_candidate` 作为 transparent group 的附加 confidence，但不得创建 Figma Auto Layout。

### M29 Design Tokens

`backend/app/design_token_report/` 是 M29 materialization 之后、asset publish 之前的 report-only single-page token candidate surface。它消费：

```text
M29 plan-driven DSL
M29 materialization report
M29.5 replay plan
```

它创建：

```text
storage/upload_previews/{taskId}/m29_design_tokens/design_token_report.json
```

模块边界：

```text
pipeline.py: report extraction orchestration and JSON write
types.py: result type
traversal.py: visible DSL element traversal and child group collection
colors.py: hex color candidate collection
text_styles.py: text style candidate collection
radius.py: radius candidate collection
spacing.py: same-parent positive gap candidate collection
report.py: summary counts and report-only invariant fields
validation.py: report schema and read-only invariant checks
```

这个 package 只报告单页 token candidates，不改 DSL，不绑定 Figma variables，不做多页 token merge，不被 Renderer 或 Figma 消费。

### M29 B-Stage Quality

`backend/app/b_stage_quality_report/` 是 B 阶段 report-only quality summary surface。它消费：

```text
M29 ownership conservation report
M29 hierarchy candidate report
M29 sibling group candidate report
M29 layout energy report
M29 Auto Layout permission report
M29 design token report
M29 materialization report
```

它创建：

```text
storage/upload_previews/{taskId}/m29_b_stage_quality/b_stage_quality_report.json
```

模块边界：

```text
pipeline.py: report extraction orchestration and JSON write
types.py: result type
summary.py: safe summary and warning extraction helpers
quality.py: quality score, risk summary, repair-cost, and maturity summary
report.py: top-level summary fields and report-only invariant fields
validation.py: report schema and read-only invariant checks
```

这个 package 只报告 quality/repair-cost，不改 DSL，不阻断 upload-preview，不创建任何 Figma 结构，不被 Renderer 或 Figma 消费。

Repair cost 只统计 actionable materialization skips。`diagnostic_only`、`fallback_only`、`preserve_in_parent_raster` 和 `suppress_duplicate` 是 M29.5 明确选择的非可见/非物化动作，不应按每个 skipped item 拉低质量分；report 仍保留 total/non-actionable skip counts 供审计。

### M29 DSL Visual Comparison

`backend/app/dsl_visual_comparison/` 是 C-stage upload-preview artifact surface。它消费：

```text
source PNG
final materialized DSL after asset publish
published local assets
```

它创建：

```text
storage/upload_previews/{taskId}/m29_dsl_visual_comparison/dsl_visual_comparison_report.json
storage/upload_previews/{taskId}/m29_dsl_visual_comparison/dsl_render.png
storage/upload_previews/{taskId}/m29_dsl_visual_comparison/source_diff.png
storage/upload_previews/{taskId}/m29_dsl_visual_comparison/source_gate_diff.png
```

模块边界：

```text
pipeline.py: DSL render/diff orchestration, report write, summary metrics
render.py: standard-library approximate DSL rasterization for image/shape/text/group/frame
```

这个 package 不改 DSL，不参与 Figma rendering。它给 real-sample batch validation 提供最终 DSL 与原图的可审计视觉差异指标。

报告保留两类指标：

```text
full-image diff: normalizedMeanAbsError / changedPixelRatio10
non-text gate diff: gateNormalizedMeanAbsError / gateChangedPixelRatio10
```

full-image diff 是诊断面，包含 report-only approximate text renderer 的字体/字形误差。`source_gate_diff.png` 是对应 `gate*` 指标的 text-excluded diff artifact：visible DSL text bboxes 和 source OCR text bboxes 覆盖的像素会被清零，用于人工查看非文字结构差异。`gate*` 指标会根据同一个 exclusion mask 判断非文字视觉结构是否退化；如果文本 mask 覆盖后没有任何 non-text 像素，gate 指标回退到 full-image diff，并记录 `gateFallbackReason=no_non_text_pixels`，避免 all-text 样本产生假 0。

source OCR text bbox 只用于 `dsl_visual_comparison` 的验证 mask，不改变 OCR、M29 ownership、DSL、素材、M29.5 replay plan 或 materializer cleanup。报告会记录 `sourceTextBboxCount` 和 `textExclusionSource=dsl_visible_text_plus_source_ocr_text`，方便 batch ledger 判断 gate 指标是否来自完整文本排除合同。

这不是字体识别、OCR 修复或 text quality acceptance。文字正确性仍必须由 OCR/source ownership/cleanup/Figma-visible validation 证明。

### Historical M29 Audit Packages

Some pre-mainline M29 audit modules remain in the repository as regression harnesses and evidence contracts. They are not active product API routes, but their public imports stay stable for tests and archival validation.

Current status:

```text
active runtime:
  none of these packages should be imported by upload_preview, source_ui_physical_graph, m29_replay_plan, or plan_materializer

compat-only:
  text_masked_media_audit
  text_aware_visual_object_refinement
  visual_object_candidate_audit
  symbol_fragment_grouping
  text_visual_ownership_gate
  visual_evidence_normalization

deletion rule:
  delete or archive only in a separate cleanup plan after import/test inventory and migration of any useful formulas into the current M29 source-chain modules
```

`backend/app/text_aware_visual_object_refinement/` contains the M29.0.5 text-aware visual object refinement harness:

```text
pipeline.py: extraction entry and lookup assembly
types.py: M29.0.5 document/options/refined object dataclasses
refinement.py: source object refinement orchestration
members.py: member-level visual/text/unresolved conversion
decisions.py: object decision/risk/reason helpers
classification.py: visual kind and source shape classification helpers
geometry.py: text-overlap, bbox union, dedupe, and count helpers
artifacts.py: crops, overlays, preview sheet helpers
report.py: JSON/Markdown/meta outputs
validation.py: document and PNG artifact validation
```

`app.text_aware_visual_object_refinement` continues to export the historical public API, including `extract_text_aware_visual_object_refinement`, `validate_text_aware_visual_object_refinement_document`, and the M29.0.5 dataclasses.

`backend/app/visual_object_candidate_audit/` contains the M29.0.4 generic visual object candidate audit harness:

```text
pipeline.py: extraction entry and document assembly
types.py: M29.0.4 document/options/evidence/object/set dataclasses
evidence.py: M29.0.3 and M29.0.2 evidence node ingestion plus ownership routing
edges.py: candidate pair generation and evidence edge scoring
candidates.py: visual/text object candidate construction and dedupe
sets.py: row/repeated set candidate construction
geometry.py: bbox, alignment, text, count, and dedupe helpers
artifacts.py: object crops, overlays, preview sheet helpers
report.py: JSON/Markdown/meta outputs
validation.py: document and PNG artifact validation
```

`app.visual_object_candidate_audit` continues to export the historical public API, including `extract_visual_object_candidate_audit`, `validate_visual_object_candidate_audit_document`, and the M29.0.4 dataclasses.

`backend/app/symbol_fragment_grouping/` contains the M29.1 symbol fragment grouping harness:

```text
pipeline.py: extraction entry and document assembly
types.py: M29.1 options/candidate/edge/group/audit dataclasses
candidates.py: M29 symbol and eligible blocked-fragment candidate collection
lineage.py: candidate/group/interactive-shape source lineage helpers
edges.py: fragment neighbor edge scoring and hard boundary checks
groups.py: accepted/uncertain/rejected symbol group construction
icon_button.py: interactive shape plus foreground symbol grouping
assets.py: accepted group crop export and asset audit
artifacts.py: JSON/Markdown outputs, overlays, preview sheet helpers
geometry.py: bbox, container, interaction, merge, and confidence helpers
validation.py: M29.1 document and artifact validation
```

`app.symbol_fragment_grouping` continues to export the historical public API, including `extract_m291_symbol_fragment_grouping`, `validate_m291_document`, and the M29.1 dataclasses.

`backend/app/text_masked_media_audit/` contains the M29.0.2 text-masked media audit harness and a compatibility OCR text-box adapter re-export:

```text
pipeline.py: extraction entry, before/after raw M29 runs, document assembly
types.py: M29.0.2 options/region/evidence/debug/document dataclasses
ocr_text.py: compatibility re-export of `app.ocr.text_boxes_from_ocr_document`
regions.py: default regions, text suppression, bbox/metrics parsing, count extraction
evidence.py: media evidence collection from M29, M29.1, blocked, and text-suppressed outputs
artifacts.py: text mask, before/after overlays, evidence overlay, preview sheet helpers
report.py: JSON/Markdown/meta outputs
validation.py: document and PNG artifact validation
```

`app.text_masked_media_audit` continues to export the historical public API. `text_boxes_from_ocr_document` remains available there for legacy audit tests, but current mainline code must import it from `app.ocr`.

`backend/app/text_visual_ownership_gate/` contains the M29.0.7 text/visual ownership routing harness:

```text
pipeline.py: extraction entry and document assembly
types.py: M29.0.7 options/decision/debug/document dataclasses
decision.py: text-box and visual-item ownership decisions
overlap.py: text-union overlap math
routing.py: routing views and audit rows
artifacts.py: ownership examples, overlays, preview sheet helpers
report.py: JSON/Markdown outputs
validation.py: document, meta, unique-id, and PNG artifact validation
```

`app.text_visual_ownership_gate` continues to export the historical public API, including `extract_text_visual_ownership_gate`, `validate_text_visual_ownership_gate_document`, and the M29.0.7 dataclasses.

`backend/app/visual_evidence_normalization/` contains the M29.0.3 visual evidence normalization harness:

```text
pipeline.py: extraction entry and normalized item assembly
types.py: M29.0.3 options/item/debug/document dataclasses
classification.py: evidence bucket decision logic
lineage.py: M29.1 lineage lookup, normalization, rejection, and bbox matching
text_overlap.py: OCR overlap, token, and counter-evidence helpers
parsing.py: source/bbox/metrics parsing and item id/confidence helpers
groups.py: visual kind, decision, and region grouping summary
artifacts.py: crop export, overlays, preview sheet helpers
report.py: JSON/Markdown/meta outputs
validation.py: document and PNG artifact validation
```

`app.visual_evidence_normalization` continues to export the historical public API. `parse_bbox` and `parse_metrics` remain compatibility exports used by older M29 audit packages.

## M29 Plan Materialization

`backend/app/plan_materializer/` is the current formal DSL producer. It consumes:

```text
source PNG
OCR
raw M29 nodes
M29.2 source objects
M29.5 replay plan
```

It creates:

```text
storage/upload_previews/{taskId}/materialized_design/design.dsl.json
storage/upload_previews/{taskId}/materialized_design/materialization_report.json
storage/upload_previews/{taskId}/materialized_design/assets/
```

Package responsibilities:

```text
builder.py: entry flow, output write, base DSL namespacing
background.py: source background, text background, foreground, shape fill/radius evidence consumption and fallback sampling
replay.py: M29.5 plan item to DSL node conversion
assets.py: raster/icon asset crop, copy, local URL helpers
cleanup.py: plan-authorized fallback and copied image cleanup execution
report.py: materialization summary/report helpers
types.py: options/result/replay node dataclasses
```

It owns:

```text
source background sampling
visible node append from M29.5 plan
source-proven shape fill/radius replay
raster/media/icon crop or asset copy
plan-authorized fallback cleanup
plan-authorized copied image asset text cleanup
plan-authorized copied image asset promoted-internal alpha-mask cleanup
report building
```

Shape replay style priority is:

```text
M29.2 sourceEvidence.shapeFillOverride / shapeRadiusOverride
-> raw M29 source node style.fill and geometry radius
-> fallback pixel sampling from the source PNG bbox
```

The materializer must not discard raw M29 `style.fill` and resample the whole bbox when a source shape already provided stable fill evidence. Bbox mean sampling is only a fallback, because support/control bboxes commonly contain text, icons, photos, or darker foreground pixels that would contaminate the replayed shape color.

Copied-image cleanup risk is decided before materialization by final M29.5. If a promoted internal icon has risky alpha metrics, high text overlap, or a shape marker lacks replacement style evidence, M29.5 keeps the visible replay item but omits the copied-image cleanup target and records a `cleanup_rejected_*` risk. The materializer must continue to execute only the cleanup targets present in the plan.

It must not own:

```text
text editability classification
contains/overlap cleanup authorization
new bbox generation
semantic component inference
theme/color/text-specific patching
```

`backend/app/m29_materialization_utils.py` contains neutral helpers shared by M29.2 and the materializer. Keep it free of source ownership policy.

## Platform, API, Storage

平台和通用支持文件：

```text
backend/app/config.py
backend/app/database.py
backend/app/state.py
backend/app/storage.py
backend/app/png_tools/
backend/app/ocr.py
backend/app/ocr_baidu.py
backend/app/errors.py
```

这些文件不应承载 M29 业务规则。新增 owner、relation、shape replay 或 materialization 策略时，优先放回对应 M29 contract layer。

`backend/app/png_tools/` 是标准库 PNG 支持包，只负责 metadata、decode、encode、crop/fill、background/foreground sampling 和 small geometry helpers；它不承载 source ownership 或 replay policy。

## Go Codia-like Compiler Validation

`services/backend-go/cmd/codiaanalyze` 是 Codia-like compiler rebuild 的第一阶段验证工具。它读取原始 Codia/Figma canvas JSON，定位 `Figma design - ... / Root`，解析 `pluginData` 中的 `schema:id`，并输出：

```text
codia_canvas_analysis.v1.json
codia_canvas_analysis_report.md
codia_ir.v1.json
codia_figma_like_tree.v1.json
```

该 analyzer 是新的结构验收基础，而不是旧 `m29visualtree` 的调参工具。它检查 node/type/name/role 计数、`guid` 与 `schema:id` 覆盖、schema suffix 连续性、children suffix 降序、Button/EditText child mode、TextView name/characters、IMAGE fill/hash、background last-child、parent-child overflow、sibling overlap，以及 role 到 visible Figma type/name 的映射闭包。

`codia_ir.v1.json` 是 raw canvas 到 role-aware IR 的 golden replay 输入。每个节点保留 `role`、`source_bbox`、`figma_bbox`、`schema_id`、`seq`、source guid/path、evidence、style/text/asset，以及有序 children。`source_bbox` 的 x/y 优先来自 `schema:id`，`figma_bbox` 来自实际 transform/size，用于保留目标规格要求的双 bbox 轨道。

`codia_figma_like_tree.v1.json` 是 IR 发射出的受控 Figma-like 树，只覆盖 `FRAME`、`TEXT`、`ROUNDED_RECTANGLE` 三类节点和 Codia-like visible name 闭包。它不是完整 `.canvas.json` 序列化；它的职责是在引入 Figma Plugin API emitter 之前验证 role/type/name/schema/bbox/order 合同。

018 golden baseline 可用以下命令做 hard check：

```bash
cd services/backend-go
go run ./cmd/codiaanalyze \
  -input /Users/luhui/Downloads/figma/json/腾讯动漫_018_1440.json \
  -out /tmp/codia-analyze-018 \
  -expect tencent-comic-018
```

`-expect tencent-comic-018` 会验证 `docs/product/codia_compiler_buildability_audit_zh.md` 中的 018 hard checks。其他 raw canvas samples 应先生成各自 baseline，再只套 cross-sample invariants；不要把 018/022 的固定节点数、root child count、具体 role 分布当全局规则。

后续 Codia-like compiler work 应从 analyzer 进入 role-aware IR / emitter，而不是继续把 XY-cut 或 low-evidence synthetic groups 当主干。

`services/backend-go/cmd/codialeaves` 是 Phase 3 的 M29 evidence -> Codia leaf IR 入口。它只读取 `evidence_tokens.v1.json`，把 `text_token` 转为 `TextView`，把 `raster_region_token` / `symbol_cluster_token` 转为 `ImageView`，把 `surface_region_token` / `layer_background_token` 转为 `Background`，并写出：

```text
codia_leaf_ir.v1.json
codia_leaf_ir_report.md
codia_figma_like_tree.v1.json
```

`codia_leaf_ir.v1.json` 仍是标准 `CodiaIR` 文档，只是文件名标明来源是 M29 evidence tokens。该阶段不合成 `Button`、`EditText`、`ListView`、`ActionBar`、`StatusBar`、`BottomNavigation` 或 residual `ViewGroup`；这些必须在后续 control synthesis / region classifier 中基于明确证据完成，不能退回 XY-cut 猜结构。

`services/backend-go/cmd/codiacontrols` 是 Phase 4 的 control synthesis 入口。它读取 `codia_leaf_ir.v1.json`，只在已有 `Background` / control-surface candidate 且内部存在 foreground text/image/icon evidence 时合成 `Button` 或 `EditText`，并把 `bg_Button` / `bg_EditText` 放为 owner-local last child。输出：

```text
codia_control_stage.v1.json
codia_control_ir.v1.json
codia_control_ir_report.md
codia_figma_like_tree.v1.json
```

`codia_control_stage.v1.json` 是该阶段的真实合同，包含 `controls`、`remaining`、`rejections` 和 `diagnostics`。`codia_control_ir.v1.json` 是由 stage result 组装出的兼容调试快照，便于继续用 emitter 和旧 CLI 检查 visible tree；最终 root/body/list/card ownership 仍属于 `internal/codia/tree`，不属于 control synthesis。

该阶段仍禁止从 text bbox 单独创造结构背景。真实样本验证显示，若某个 Codia 控件在 M29 evidence 中缺少背景 surface token，`codiacontrols` 会保持漏检；修复点应回到 physical evidence / control-surface detection，而不是在 control synthesis 里按文案、样本坐标或固定尺寸硬造控件。

Go M29 physical evidence now emits control-surface candidates for OCR-local low-texture controls、compact foreground anchored horizontal controls, and local-contrast colored/gradient pill controls. `codialeaves` preserves those as `control_surface_background` evidence. `codiacontrols` then applies permission gates over that evidence: wide `EditText` beats local glyph buttons, wide action-button surfaces beat inner text-only surfaces, owner-local duplicate backgrounds are consumed, obvious numeric/price text-only controls are rejected, tall non-wide-action content panels with vertically biased or multi-line foreground are kept as leaves instead of being upgraded to `Button`, and text-only near-fill surfaces without meaningful backplate padding are rejected while URL-like chrome pills remain valid controls.

Current Phase 4 validation against raw Codia golden IR is:

| sample | golden controls | synthesized controls | matched @ IoU >= 0.6 | known gap |
| --- | ---: | ---: | ---: | --- |
| Tencent 022 | 5 | 5 | 5 | no remaining generated `Button` extra in the current 022 smoke |
| Tencent 018 | 9 | 7 | 7 | two bottom benefit buttons still missing; rejected panel backgrounds still need background/card ownership cleanup |

These remaining misses/extras are owned by physical evidence, background/card ownership, and the next region/list/card permission layer. Do not push them back into `xycut`, and do not reintroduce text-bbox-only background synthesis.

The current Go Codia-like compiler path is:

```text
internal/codia/diff       // generated CodiaIR vs golden CodiaIR structural diff
cmd/codiadiff             // standalone diff CLI
internal/codia/audit      // read-only failure audit over structural diff
cmd/codiaaudit            // standalone failure audit CLI
internal/codia/compiler   // screenshot evidence -> CodiaIR orchestration
cmd/codiacompile          // end-to-end local compiler CLI
internal/codia/tree       // ActionBar/StatusBar/BottomNavigation/ListView/ViewGroup tree builder
```

The intended compiler path is:

```text
input PNG + OCR
-> Go M29 physical evidence
-> M29 evidence tokens
-> Codia leaves
-> Codia control stage result
-> Codia tree builder
-> Codia Figma-like tree
-> optional golden structural diff
```

`codiacompile` must write a `CodiaIR` tree, a Figma-like tree, and when a golden IR is provided:

```text
codia_structure_diff.v1.json
codia_structure_diff_report.md
codia_failure_audit.v1.json
codia_failure_audit_report.md
```

The structural diff is the release gate for role vocabulary, role precision/recall, control/background ownership, parent edges, bbox IoU by role, foreground-first/background-late ordering, and extra/missed nodes by role. Golden raw Codia data is validation-only; it must not be read by generation logic.

`services/backend-go/cmd/codiaaudit` is a read-only diagnostic CLI over `codia_structure_diff.v1.json`. It aggregates existing diff failures by owning layer, diagnosis, role, evidence kind, and IoU bucket, then emits ranked action items. It does not read raw Codia canvas JSON and is not part of generation decisions. Its current purpose is to route the next fixes away from blind tree/threshold edits and toward the layer that lost information.

`internal/codia/tree` is the first role-aware tree builder. It consumes the control stage result rather than treating control synthesis as a final root tree, creates top chrome (`ActionBar` or `StatusBar` wrapper depending on evidence), `BottomNavigation`, main `ListView`, row/list `ViewGroup` containers, applies foreground-first/background-late ordering, assigns deterministic reverse-children DFS schema sequence, and filters obvious final-tree physical noise while preserving the source evidence in leaf/control artifacts. Tree-created containers carry proposal evidence such as `body_list_owner`, `bottom_navigation_candidate`, `repeated_row_list`, `repeated_row_item`, and `major_section_owner`; `codia_tree_ir_report.md` summarizes these counts under `Tree Evidence`, and `codia_structure_diff` preserves `evidenceKind` on generated/golden node matches. It is intentionally not an XY-cut wrapper and it is not allowed to read golden canvas data during generation.

Within repeated-row item containers, the tree builder also merges vertically adjacent and horizontally aligned `control_surface_background` fragments into a single card `Background`. This fixes the common split-background case where physical evidence sees upper/lower surface pieces but Codia emits one card backplate. The merge is constrained to same-item `control_surface_background` leaves and does not affect `Button` / `bg_Button` ownership.

For right-side floating rails, the tree builder can emit a root-level side `ListView`, an inner `ListView`, and a stack `ViewGroup` when a search-top page exposes right-edge marker evidence plus rail-local image/control/text evidence. The inner rail uses the IR dual-bbox contract: source coordinates preserve detector-like rail coordinates, while figma coordinates fit the emitted Codia-like structural match. Current validation matches Tencent 022's side rail outer `ListView`, inner `ListView`, and stack `ViewGroup`; remaining rail item misses are owned by upstream leaf evidence because the current M29 artifacts do not expose the individual vertical cover crops.

Current screenshot-derived compiler smoke against raw golden IR:

| sample | generated nodes | golden nodes | matched | extra | missed | parent edge precision | parent edge recall | structural roles now matched |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Tencent 018 | 150 | 146 | 90 | 60 | 56 | 0.409 | 0.421 | `ActionBar`, `BottomNavigation`, `ListView`, `ViewGroup`; generated `Button` precision is now 1.00 |
| Tencent 022 | 102 | 120 | 82 | 20 | 38 | 0.554 | 0.471 | `StatusBar`, `BottomNavigation`, `ListView`, side rail `ListView`, `ViewGroup`; generated `Button` precision is now 1.00 |

Current failure audit over the same smoke:

| sample | top owning layer | dominant diagnosis | count | implication |
| --- | --- | --- | ---: | --- |
| Tencent 018 | `m29_physical_evidence_or_codia_leaf` | `upstream_leaf_missing ImageView` | 14 | Source primitive / leaf crop extraction lacks Codia-like ImageView crops. |
| Tencent 018 | `background_detection_or_permission` | `background_fragment_extra` | 16 | Background fragments need merge/consume/suppress policy before final tree output. |
| Tencent 022 | `m29_physical_evidence_or_codia_leaf` | `upstream_leaf_missing ImageView` | 20 | Right rail and body internal cover crops are missing upstream evidence. |
| Tencent 022 | `codia_tree_builder` | `tree_container_bbox_mismatch ViewGroup` | 8 | Tree bbox fitting remains, but should follow leaf crop recall improvement. |

The remaining dominant gaps are not owned by `m29visualtree`: physical leaf bbox mismatch, missing large Background surfaces, rejected control-surface backgrounds that still need card/background ownership cleanup, over-broad card/row grouping, and missing rail/list item crops from upstream leaf evidence. Next work should refine `internal/codia/tree` ownership and upstream physical evidence; do not solve these by tuning XY-cut thresholds or by injecting Codia golden identity into generation.

Latest evidence-kind breakdown for extra generated nodes shows where the next tree ownership work belongs:

| sample | dominant structural extra evidence | dominant leaf/control extra evidence |
| --- | --- | --- |
| Tencent 018 | `repeated_row_item 1`, `major_section_owner 1` | `image_or_icon_crop 24`, `ocr_text 9`, `control_surface_background 9`, `solid_background 5` |
| Tencent 022 | none from repeated row/list or side rail containers | `ocr_text 10`, `control_surface_background 4`, `image_or_icon_crop 3`, `solid_background 1` |

## Go M29 VisualTree Diagnostics

`services/backend-go/cmd/m29visualtree` 是 Go M29 VisualTree 的 legacy diagnostic CLI，不是新的 Codia-like compiler 主线。它消费 `evidence_tokens.v1.json` 和 `relation_graph.v1.json`，输出 `visual_tree.v1.json`、`visual_element.v1.json`、overlay/report artifacts，并额外写 report-only 决策追踪：

```text
visual_tree_trace.v1.jsonl
visual_tree_trace_report.md
```

trace 解释 containment、background split、text/background pairing、XY-cut、neighbor components、cluster wrap/flatten、skip xycut 和 straggler absorb 等结构决策。它只用于诊断和批量评测归因，不改变 VisualTree、VisualElement、DSL、assets、M29.5 plan 或 materializer 行为。

VisualTree synthetic groups 会在 `meta` / `processingMeta` 中暴露 `groupRole`、`parentReason` 和 `evidenceScore`。当前 group permission gate 只在 Go VisualTree 输出前做窄范围结构折叠:低证据 `text_background_group` 会回退为原 text child，来自 `xycut` / `neighbor_component` 且无文字后代的退化薄片 `spatial_group` 会回退为其 children。该 gate 不读取 Codia guid、Codia bbox、样本名、文案或固定坐标，也不改变 M29 source ownership、M29.5 replay plan、Renderer 或 plugin。

`services/backend-go/cmd/m29trace` 是只读查询工具，可用 `-node` 追踪一个 synthetic group 的创建原因，也可叠加 `compare_trees.py --trace-dir` 生成的 eval trace 查看 `matched/extra`、best Codia IoU 和对应 Codia bbox。eval trace 中的 normalized Go/Codia 节点保留 `id`、`sourceId`、`path`、`parentId`，用于稳定定位 Codia reference node 和 Go container；这些身份字段只属于评测诊断层，不进入 VisualTree runtime 输出。

`services/backend-go/tools/compare_trees.py --batch` 的 score 公式仍是 `0.7*recall + 0.3*depth_ratio`，同时输出诊断用 precision、F1、container ratio，并在 eval trace summary 中写入 `goPrecision`、`f1`、`containerRatio` 和 `extraByGroupKind`。

`services/backend-go/tools/audit_group_evidence.py` 是离线分析工具。它只读取 `visual_tree.v1.json`、`visual_tree_trace.v1.jsonl` 和 `compare_trees.py --trace-dir` 生成的 eval trace，按 Go `nodeId` join 当前树节点、create event 和 `matched/extra` verdict，输出 `parentReason`、`spatialDepth`、`childCount`、`containsText`、`shortSide`、`areaRatio`、`childKinds` 分布和候选规则 backtest。该工具不要求 Go compiler 写新的 runtime artifact，也不把 Codia identity/bbox 输入 VisualTree runtime。

## Removed Runtime Boundary

These modules or product paths have been removed from active backend runtime:

```text
M29 Direct compare replay
legacy M30 evidence-grounded materialization
mixed symbol/text M30 guard
M29.0.x legacy bridge
reconstruction UI tree
hierarchy readiness
hierarchy materialization
content/chrome classification
unit structure readiness
ONNX box proposer
```

相关 ADR 和 completed plans 只说明历史尝试。后续若重新做 hierarchy、unit、component 或 Codia adapter，需要从当前 M29 source truth 重新建计划和测试合同。

## Legacy Diagnostic Boundary

M20-M28、旧 icon/slice/provider harness、visual provider benchmark、mask proposal experiments 和已删除 downstream structure experiments 已经降级为历史证据或 ADR 背景。当前 backend active runtime 不应依赖它们提供 source ownership。

保留历史文档的目的只有两个：

```text
追溯为什么从旧 icon/slice/provider/downstream route 转向 M29 pixel topology
避免后续重复把 provider proposal 或 weak downstream grouping 当 source truth
```

## Next Refactor Direction

代码瘦身应单独开阶段，且默认先做无行为变更拆分。优先顺序：

1. `upload_preview/`：继续保持薄编排；后续如需调整 stage 顺序必须单独开行为阶段。
2. 若继续瘦身 M29 主链，优先针对已有 domain package 内仍接近压力线的职责模块开单独 no-behavior phase，不做跨领域 helper consolidation。

每次拆分都必须先有 focused tests，且 diff 应证明 output contract 不变。
