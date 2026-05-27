# Current Mainline Code Map

本文档只描述当前代码职责和阅读顺序，作为后续拆分长文件的依据。它不引入新 runtime stage、不改变 API、不替代架构文档。

当前事实链：

```text
Plugin upload
-> backend/app/upload_preview/
-> OCR
-> M29 perception model report
-> raw M29 primitive graph
-> M29.2 ownership
-> M29 perception source compiler
-> M29.3 relation
-> M29.4 weak cluster
-> M29.5 replay plan
-> M29 ownership conservation report
-> M29 hierarchy candidate report
-> M29 sibling group candidate report
-> M29 layout energy report
-> M29 Auto Layout permission report
-> M29 plan-driven materializer
-> M29 perception fate trace report
-> DSL v0.1
-> Renderer
```

M29 Direct compare, legacy M30 materialization, M31-M39/M39.1 downstream experiments, the legacy ONNX proposer, and the old M29.6/transparent/evidence/promotion rerun loop have been pruned from active backend runtime.

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
run M29 perception model report by default
run M29/M29.2/M29.3/M29.4/M29.5
compile perception candidates into enhanced M29.2 source ownership by default
run M29 ownership conservation report
run M29 hierarchy candidate report
run M29 sibling group candidate report
run M29 layout energy report
run M29 Auto Layout permission report
run M29 plan-driven materialization
run M29 perception fate trace report by default
optionally run M29 design token, B-stage quality, and DSL visual comparison in diagnostic/full mode
publish M29 assets
write task status and stage timings
```

模块边界：

```text
pipeline.py: upload preview 主编排顺序
types.py: pipeline error/profile/runtime/artifact policy 类型
paths.py: upload preview storage path layout
timings.py: stage timing record/write logic
task_state.py: task status/error/completion writes
stages.py: OCR/M29/M29.2/M29.3/M29.4/M29.5/perception-model/perception-source-compiler/ownership-conservation/hierarchy-candidate/sibling-group/layout-energy/auto-layout-permission/materialization/perception-fate-trace/design-token/B-stage-quality/DSL-visual-comparison stage wrappers
assets.py: M29 materialized assets publish
```

这些模块不承载 owner、relation、cleanup 授权或 materialization 策略。

`UPLOAD_PREVIEW_RUNTIME_MODE=interactive` is the default model-first runtime. `diagnostic` and `full` run additional post-materialization quality artifacts, but they do not restore the legacy M29.6 -> transparent -> evidence -> promotion -> promoted rerun chain.

OCR document to M29 text-box conversion is owned by `backend/app/ocr.py` via `text_boxes_from_ocr_document`. Current mainline packages must import that adapter from `app.ocr`, not from historical M29 audit packages.

## Source Truth Layer

### Default M29 Model-First Perception

`backend/app/perception_model_report/` is the default report-only perception proposal layer. It runs when:

```text
M29_PERCEPTION_MODEL_ENABLED=true  # default
M29_PERCEPTION_MODEL_PATH=<local ONNX model path>
```

It consumes the source PNG and emits normalized model candidates:

```text
storage/upload_previews/{taskId}/m29_perception_model/perception_model_report.json
```

It does not create DSL nodes, assets, source ownership, replay authorization, or cleanup authorization. `onnxruntime` is a backend dependency because the model-first path is now the normal local runtime. Compatibility isolation can set `M29_PERCEPTION_MODEL_ENABLED=false`.

`backend/app/perception_source_compiler/` is the M29.2 ownership compiler for model-first candidates. It consumes:

```text
OCR document
source PNG pixels
perception_model_report
current M29.2 source document
```

It emits:

```text
storage/upload_previews/{taskId}/m29_perception_source_compiler/perception_source_compiler_report.json
storage/upload_previews/{taskId}/m29_perception_source_compiler/source_ui_physical_graph.perception.json
```

Allowed compiled source ownership:

```text
control_background / shape_geometry / shape_replay
media_region / preserve_raster / image_replay for complex selectable control crops
raster_icon / raster_icon / icon_replay
small indicator shape / shape_geometry / shape_replay
```

The compiler is upstream of final M29.3/M29.4/M29.5. It does not create DSL nodes, does not authorize cleanup directly, and does not let materializer consume raw model output. M29.5 remains the only visible replay and cleanup authority.

`backend/app/m29_perception_fate_trace/` is a read-only diagnostic surface after materialization. It joins:

```text
perception candidate
-> perception source compiler decision
-> final M29.5 replay decision
-> cleanup decision
-> materializer result
```

It writes:

```text
storage/upload_previews/{taskId}/m29_perception_fate_trace/perception_fate_trace_report.json
```

It must remain diagnostic only. It does not feed promotion, M29.5, materializer, Renderer, or plugin decisions.

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

显式 compat 调用时创建：

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

### Legacy M29.6 Media Internal Decomposition

`backend/app/media_internal_decomposition/` 是旧的 pre-model composite-media evidence surface。它不再由 active upload-preview pipeline 调用。保留该 package 仅用于旧测试、归档审计或显式迁移对照。

```text
OCR blocks
source PNG pixels
raw M29 primitive nodes and blocked evidence
M29.2 source objects
M29.3.1 relation graph metadata
M29.5 replay plan metadata
```

显式 compat 调用时创建：

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

这个 package 只报告 `preserve_raster` media 内部 OCR/text-mask/raw symbol/shape/unknown candidate evidence，以及非 OCR internal foreground component evidence。它不得重新接入默认主链，不得创建 DSL nodes，不改 M29.5 plan，不生成 active assets，不提升 source ownership，不授权 cleanup，不被 materializer 消费。模型优先后，媒体内控件应由 `perception_model_report` 和 `perception_source_compiler` 在 M29.2 之前解决。

M29.6 report meta 记录 `scaleProfile`。Text mask padding、pixel component min/max area、short-edge gate、generic scan window size、generic candidate budget、connected component return budget 都使用该内部 scale profile 或面积密度预算。比例证据仍保持比例形式：overlap ratio、containment ratio、aspect ratio、coverage、text overlap、hero penalty 和 cleanup risk 不应被改成固定样本规则。

### Legacy M29 Transparent Asset Report

`backend/app/transparent_asset_report/` 是旧 M29.6 loop 的 transparent asset evidence surface。它不再由 active upload-preview pipeline 调用。后续若需要 alpha/mask 能力，应重定位为 accepted perception candidate 的 asset/mask builder，而不是候选发现或 visible replay gate。

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
visibleReplayEligible: legacy evidence/promotion loop 的可见回放证据字段；默认 model-first upload-preview 不消费
cleanupEligible: 永远 false；cleanup 只能由 final M29.5 replay plan 授权
```

`decision=allow` 和 `assetPath` 只表示诊断 alpha asset 生成成功。只有显式维护 legacy loop 时才应读取 `visibleReplayEligible`；默认 model-first runtime 不读取 transparent report 决策。

Transparent asset report meta 记录 `scaleProfile`。Preflight 的 candidate area 和 short-edge gate 使用同一内部 scale profile，避免高倍率 UI icon 因 1x 面积/短边上限被误拒。Alpha 背景稳定性、edge-alpha、foreground coverage 和 connected-foreground 仍是像素质量 gate，不因为 scale 成功就授权 visible replay 或 cleanup。

### Legacy M29 Evidence Contract

`backend/app/m29_evidence_contract/` 是旧 M29.6/transparent evidence 与 internal source promotion 之间的 report-only 证据合同层。它不再由 active upload-preview pipeline 调用。后续证据合同应改造为 perception candidate verifier，验证模型候选是否可进入 M29.2 source ownership。

```text
M29.2 source objects
M29.6 media internal decomposition report
M29 transparent asset report
```

显式 compat 调用时创建：

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

这个 package 把 internal UI icon 候选的 source score、size/compactness、text-anchor relation、same-media containment、repetition、transparent visible replay eligibility、text-overlap penalty、hero/texture penalty、cleanup risk 和 repair-cost penalty 合成 legacy `allow_visible_replay` / `report_only` / `reject`。它也把 M29.6 明确标注的 shape role，例如 `selected_marker_candidate`、`status_dot_candidate`、`table_marker_candidate`，用 role support、compactness、repetition、same-media containment、text-overlap 和 hero/texture penalty 合成 legacy shape replay 合同；shape role 不要求 transparent PNG。Generic `pixel_component/non_ocr_foreground` 只能作为 report/reject 证据，不能仅凭 alpha asset 生成成功直接 visible replay，避免地图路线、楼层线、下划线等媒体碎片被误升成图标或 shape。它不创建 source objects，不改 DSL，不改 assets，不授权 cleanup，不被 materializer 直接消费。默认 model-first runtime 不消费该报告；未来若显式维护 legacy loop，`allow_visible_replay` 也只能作为 legacy internal_source_promotion 的输入。

### Legacy M29 Internal Source Promotion

`backend/app/internal_source_promotion/` 是旧 M29.6/transparent/evidence-contract evidence 回到 M29.2 source ownership 的 compatibility bridge。Active model-first runtime 使用 `backend/app/perception_source_compiler/` 在更早的 M29.2 边界完成 source ownership 编译；不要把这两个桥混在一起，也不要恢复 promotion rerun 作为默认主链。

```text
M29.2 source objects
M29.6 media internal decomposition report
M29 transparent asset report
M29 evidence contract report
```

显式 compat 调用时创建：

```text
storage/upload_previews/{taskId}/m29_internal_source_promotion/internal_source_promotion_report.json
storage/upload_previews/{taskId}/m29_internal_source_promotion/source_ui_physical_graph.promoted.json
```

模块边界：

```text
pipeline.py: internal icon promotion and promoted M29.2 document write
types.py: promotion result and invariant metadata
```

这个 package 提升两类 M29.6 internal candidate。Icon path 仍只提升同时满足 M29.6 accepted `internal_icon_candidate`、transparent `visibleReplayEligible=true`，以及 evidence contract `allow_visible_replay` 的对象；若 transparent asset report 提供 `analysisBbox`，promotion 使用该 bbox 作为 promoted source bbox，并在 source evidence 中保留原始 `candidateBbox`，保证带上下文 padding 的透明 PNG 不会在 Figma 中被错误缩放。Shape path 只提升 evidence contract `allow_visible_replay` 的明确 shape role，例如 selected marker、table marker 和 status dot，写回 `shape_geometry` / `shape_replay` source object；shape path 不要求 transparent asset，也不把普通内部图块猜成按钮背景。Promotion dedupe 使用 IoU、containment、center shift 和 size drift 做 role-compatible spatial merge；同角色高重叠保留 evidence rank 更高者，不同角色高重叠记录 conflict，不静默覆盖。它不创建 DSL nodes，不绕过 M29.5，不再直接把 local confidence/alpha asset generation 当 promotion 权限。默认 upload-preview 不运行 promotion rerun；显式 legacy 对照若运行该 package，promoted document 仍必须重新经过 M29.3/M29.4/M29.5 和 ownership conservation，materializer 只能消费 final M29.5 授权结果。

### Legacy M29 Bridge Fate Trace

`backend/app/m29_bridge_fate_trace/` 是旧 M29.6 bridge 的 materialization 后 diagnostic surface。它不再由 active upload-preview pipeline 调用。Model-first regression debugging should use `m29_perception_fate_trace` first.

```text
M29.6 media internal decomposition report
M29 transparent asset report
M29 evidence contract report
M29 internal source promotion report
final M29.5 replay plan
M29 materialization report
```

显式 compat 调用时创建：

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

`backend/app/design_token_report/` 是 M29 materialization 之后的 diagnostic-mode report-only single-page token candidate surface。它消费：

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

`backend/app/b_stage_quality_report/` 是 diagnostic-mode B 阶段 report-only quality summary surface。它消费：

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

`backend/app/dsl_visual_comparison/` 是 diagnostic/full runtime C-stage upload-preview artifact surface。它消费：

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
