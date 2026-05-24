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
-> M29 plan-driven materializer
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
run M29 plan-driven materialization
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
stages.py: OCR/M29/M29.2/M29.3/M29.4/M29.5/materialization stage wrappers
assets.py: M29 materialized assets publish
```

这些模块不承载 owner、relation、cleanup 授权或 materialization 策略。

## Source Truth Layer

### Raw M29 Primitive Graph

Raw M29 的基础数学层已拆到 `backend/app/visual_primitive/`：

```text
types.py: raw M29 dataclasses and Literal contracts
bbox.py: bbox math and bbox set operations
mask.py: binary mask construction, overlap, validation, PNG export
metrics.py: region metrics, color distance, numeric clamps
pixels.py: pixel crop, region/ring sampling, debug rectangle drawing
geometry.py: shape geometry fit, support occupancy fit, radius/layer hint helpers
components.py: text exclusion mask, foreground mask, connected components, image protection mask
```

`backend/app/visual_primitive_graph.py` 仍是兼容入口和 detector orchestration 文件，继续导出 `extract_m29_visual_primitive_graph` 以及历史调用方依赖的 M29 类型和基础函数。它负责：

```text
source PNG pixel measurement
OCR text bbox ingestion
text / shape / image / symbol / unknown primitive nodes
low_contrast_support detection
text_support_background detection
source assets and overlays
```

后续拆分应继续围绕真实边界进行：

```text
support background detectors
primitive detectors
asset/export/debug artifact writers
document validation
```

拆分不能改变 primitive IDs、metrics、geometry contract、support detector gates、asset paths 或 output JSON shape。

### M29.2 Ownership

`backend/app/source_ui_physical_graph.py` 负责把 raw M29/OCR/source pixels 转成 source objects：

```text
visualKind
pixelOwner
replayDecision
source lineage
physical metrics
```

这是 source ownership gate。修文字支撑背景、深色 UI raster/media 丢失、复杂头像/图表/照片被误画成 shape 等问题时，应从 raw M29 detector 或 M29.2 owner contract 修起，不能在 materializer/Renderer/plugin 按文字内容、颜色或主题伪造。

M29.2 当前也负责把有物理证据的大型复杂 image-like unknown 恢复为 `media_region` / `preserve_raster` / `image_replay`，为 fallback-off 场景提供 raster/media preservation。

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

`backend/app/stable_design_cluster.py` 从 relation graph 产出 weak structural evidence：

```text
row_like
column_like
background_anchor_like
repeated_item_like
```

这些 cluster 是 report-only evidence，不给组件化、Auto Layout、Figma Component/Instance 或 materialization 权限。

### M29.5 Replay Plan

`backend/app/m29_replay_plan.py` 是正式 materialization 前的质量门。它负责：

```text
map M29.2 replay decisions to final plan actions
dedupe near-equal owners
sort visible replay order
enforce node budget
authorize fallback cleanup
authorize copied image asset cleanup
record risk and cluster support
```

M29.5 只写 plan，不创建 DSL visible nodes。Plan target roles are:

```text
m29_text
m29_shape
m29_image
m29_symbol
```

### Historical M29 Audit Packages

Some pre-mainline M29 audit modules remain in the repository as regression harnesses and evidence contracts. They are not active product API routes, but their public imports stay stable for tests and archival validation.

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
background.py: source background, text background, foreground, shape fill/radius sampling
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
report building
```

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
backend/app/png_tools.py
backend/app/ocr.py
backend/app/ocr_baidu.py
backend/app/errors.py
```

这些文件不应承载 M29 业务规则。新增 owner、relation、shape replay 或 materialization 策略时，优先放回对应 M29 contract layer。

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

1. `visual_primitive_graph.py`：继续按 support detectors、detectors、artifact writers 拆分；基础 types/bbox/mask/metrics/pixels、geometry fit 和 component evidence layer 已在 `visual_primitive/`。
2. `source_ui_physical_graph.py`：按 OCR text ownership、media detection、icon clustering、shape/unknown/blocked classification 拆分。
3. `upload_preview/`：继续保持薄编排；后续如需调整 stage 顺序必须单独开行为阶段。

每次拆分都必须先有 focused tests，且 diff 应证明 output contract 不变。
