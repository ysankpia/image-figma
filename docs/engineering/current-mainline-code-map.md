# Current Mainline Code Map

本文档只描述当前代码职责和阅读顺序，作为后续拆分长文件的依据。它不引入新 runtime stage、不改变 API、不替代架构文档。

当前事实链：

```text
Plugin upload
-> backend/app/m30_upload_pipeline.py
-> OCR
-> raw M29 primitive graph
-> M29.2 ownership
-> M29.3 relation
-> M29.4 weak cluster
-> M29.5 replay plan
-> M29 Direct compare variant
-> legacy M29.0.x bridge
-> M30 materialization
-> DSL v0.1
-> Renderer
```

M31-M39/M39.1 downstream experiments and ONNX proposer have been pruned from active backend runtime.

## Runtime Entry Surface

`backend/app/main.py` 装配当前 route modules：

```text
backend/app/routes/health.py
backend/app/routes/upload_m30_preview.py
backend/app/routes/tasks.py
backend/app/routes/assets.py
```

当前产品上传入口是 `POST /api/upload-m30-preview`。旧 `POST /api/upload`、旧 M8-M28 debug endpoints，以及 M31/M39/M39.1 diagnostic endpoints 已从 active runtime 移除；不要在新工作里恢复它们。

## Pipeline Orchestrator

`backend/app/m30_upload_pipeline.py` 是当前后端主编排文件。它负责：

```text
validate upload
save source PNG
run OCR
run M29/M29.2/M29.3/M29.4/M29.5
run M29 Direct compare variant
run M29.1 and M29.0.x legacy bridge stages
run M30 materialization
publish M30 and M29 Direct assets
write task status and stage timings
```

这个文件仍偏长。后续代码瘦身应优先做无行为变更拆分，例如把 artifact publishing、optional stage wrappers、pipeline path construction 和 task status error handling 拆出。不要顺手改 stage order 或 runtime contract。

## Source Truth Layer

### Raw M29 Primitive Graph

`backend/app/visual_primitive_graph.py` 生成 raw M29 primitive graph。它负责：

```text
source PNG pixel measurement
OCR text bbox ingestion
foreground masks
text / shape / image / symbol / unknown primitive nodes
low_contrast_support detection
text_support_background detection
shape geometry fitting
source assets and overlays
```

这是当前最大的 source truth 文件之一。后续拆分应围绕真实边界进行：

```text
bbox/mask math
support background detectors
shape geometry fit
primitive detectors
asset/export/debug artifact writers
document validation
```

拆分不能改变 primitive IDs、metrics、geometry contract、support detector gates、asset paths 或 output JSON shape。

### Legacy M29.0.x Bridge

这些文件仍在 M30 materialization 前运行，作用是保留和筛选 raw M29 evidence。它们是 `/dsl` 迁移期 bridge，不是新的 source truth：

```text
backend/app/symbol_fragment_grouping.py
backend/app/text_masked_media_audit.py
backend/app/visual_evidence_normalization.py
backend/app/text_visual_ownership_gate.py
backend/app/visual_object_candidate_audit.py
backend/app/text_aware_visual_object_refinement.py
```

`backend/app/mixed_symbol_text_conflict_audit.py` 仍保留，但当前只因 M30 materialization 复用 `find_forbidden_contract_terms`。不要把它当成 upload pipeline stage。

已删除的 legacy audit modules：

```text
pre-OCR symbol lineage audit
member boundary quality audit
residual mixed boundary review
```

## M29 Contract Layer

### M29.2 Ownership

`backend/app/source_ui_physical_graph.py` 负责把 raw M29/OCR/source pixels 转成 source objects：

```text
visualKind
pixelOwner
replayDecision
source lineage
physical metrics
```

这是 source ownership gate。修 `#日本旅行`、`#北京探店` 这类文字支撑背景丢失问题时，应从 raw M29 detector 或 M29.2 owner contract 修起，不能在 M30/Renderer/plugin 按文字内容或样式伪造。

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

`backend/app/m29_replay_plan.py` 是 M29 Direct 前的质量门。它负责：

```text
map M29.2 replay decisions to final plan actions
dedupe near-equal owners
sort visible replay order
enforce node budget
authorize fallback cleanup
authorize copied image asset cleanup
record risk and cluster support
```

M29.5 只写 plan，不创建 DSL visible nodes。

## M29 Direct Compare Variant

`backend/app/m29_direct_replay.py` 消费 raw M29、M29.2 和 M29.5 replay plan，生成 compare variant DSL：

```text
storage/m30_1_uploads/{taskId}/m29_direct/m29_direct_replay_dsl.json
storage/assets/{taskId}/m29_direct/
```

它只服务 `GET /api/tasks/{taskId}/m29-direct-dsl`。M29 Direct 失败不能阻断主线 `/api/tasks/{taskId}/dsl`。

## M30 Materialization

`backend/app/evidence_grounded_dsl_materialization.py` 把可信 M29/M29.0.x evidence 转成当前主线 DSL。它负责：

```text
editable text materialization
graphic text preserve decision
source-proven support shape materialization
accepted image materialization
composite media materialization
copied media asset text cleanup
fallback erasure for materialized nodes
M30 report
```

它现在也是长文件。后续可按 materializer policy 拆分：

```text
text decision/materialization
shape candidate materialization
image/composite media materialization
raster cleanup
report building
DSL node helpers
```

拆分不能新增 bbox、不能重写 M29 JSON、不能放宽 ordinary unsafe shape/text overlap，也不能把 M29.4 weak cluster 当组件权限。

## Removed Downstream Boundary

这些 downstream modules 已从 active backend runtime 删除：

```text
reconstruction UI tree
hierarchy readiness
hierarchy materialization
content/chrome classification
unit structure readiness
ONNX box proposer
```

相关 ADR 和 completed plans 只说明历史尝试。后续若重新做 hierarchy、unit、component 或 Codia adapter，需要从当前 M29 source truth 重新建计划和测试合同。

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

这些文件不应承载 M29/M30 业务规则。新增 owner、relation、shape replay 或 materialization 策略时，优先放回对应 M29/M30 contract layer。

## Legacy Diagnostic Boundary

M20-M28、旧 icon/slice/provider harness、visual provider benchmark、mask proposal experiments 和已删除 downstream structure experiments 已经降级为历史证据或 ADR 背景。当前 backend active runtime 不应依赖它们提供 source ownership。

保留历史文档的目的只有两个：

```text
追溯为什么从旧 icon/slice/provider/downstream route 转向 M29 pixel topology
避免后续重复把 provider proposal 或 weak downstream grouping 当 source truth
```

## Next Refactor Direction

代码瘦身应单独开阶段，且默认只做无行为变更拆分。优先顺序：

1. `visual_primitive_graph.py`：按 bbox/mask math、support detectors、geometry fit、detectors、artifact writers 拆分。
2. `evidence_grounded_dsl_materialization.py`：按 text/shape/image/cleanup/report policy 拆分。
3. `m30_upload_pipeline.py`：按 orchestration、artifact publish、optional stages、task state/error handling 拆分。
4. `m29_direct_replay.py`：按 plan consumption、node appenders、asset cleanup、fallback cleanup 拆分。

每次拆分都必须先有 focused tests，且 diff 应证明 output contract 不变。
