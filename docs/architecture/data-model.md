# 数据模型

v0.1 使用 SQLite 保存当前运行时索引，较大的证据和 DSL payload 写入本地 JSON 文件。

## Current Tables

Active source currently creates:

```text
tasks
assets
dsl_results
ocr_results
error_logs
```

M30.2.2 intentionally removed the old pre-M29 result tables from active schema creation. It does not migrate or delete old local SQLite files.

## tasks

Purpose: record upload and processing state.

Fields:

```text
id
status
stage
progress
message
original_filename
mime_type
file_size
upload_path
created_at
updated_at
completed_at
failed_at
```

Current status values:

```text
processing
completed
failed
```

Current preview stages include:

```text
m29_queued
ocr
m29
m29_2_source_ui_physical_graph
m29_3_relation_graph_report
m29_4_stable_design_cluster
m29_5_replay_plan
m29_materialization
m29_asset_publish
m29_completed
```

## assets

Purpose: record fetchable image assets.

Fields:

```text
id
asset_id
task_id
role
path
url
mime_type
width
height
created_at
```

Current roles are intentionally generic and DSL-driven:

```text
original
fallback_region
m29_image
m29_symbol
m29_asset
```

Other M29 materializer roles may be stored if a DSL asset provides a more specific role. They must still resolve to files under `/files/assets/*`.

M29 preview publishes image assets used by DSL to:

```text
storage/assets/{taskId}/m29/
/files/assets/{taskId}/m29/...
```

## dsl_results

Purpose: point a task at its generated DSL file.

Fields:

```text
id
task_id
dsl_path
version
validation_status
validation_errors
created_at
```

For current preview tasks, `dsl_path` points to:

```text
storage/upload_previews/{taskId}/materialized_design/design.dsl.json
```

`validation_status` is currently `valid` when the pipeline completes.

## ocr_results

Purpose: record OCR provider status and payload path.

Fields:

```text
id
task_id
provider
model
status
ocr_path
block_count
error_code
error_message
created_at
```

OCR payload path:

```text
storage/upload_previews/{taskId}/ocr/ocr.json
```

In M29 preview, OCR failure fails the task because OCR text ownership is a source fact for M29 materialization.

## error_logs

Purpose: record pipeline failures and lookup/debug errors.

Fields:

```text
id
task_id
stage
error_code
message
detail
severity
created_at
```

## File Payloads

SQLite does not store M29 evidence payloads. They live under:

```text
storage/upload_previews/{taskId}/
```

Important files:

```text
ocr/ocr.json
m29/nodes.json
m29_2/source_ui_physical_graph.json
m29_3/region_relation_graph_report.json
m29_4/stable_design_cluster_report.json
m29_5/replay_plan.json
materialized_design/design.dsl.json
materialized_design/materialization_report.json
stage_timings.json
```

The directory prefix `upload_previews` is historical storage naming. It is not a statement that the runtime still uses M30 materialization.

## Removed Tables And Payloads

The following old result tables or payload families are no longer active source contracts:

```text
primitive_results
dsl_patch_results
text_replacement_results
text_binding_results
component_structure_results
component_annotation_results
layer_separation_results
asset_slice_results
icon_candidate_results
icon_coverage_audit_results
icon_gap_candidate_results
icon_placement_plan_results
icon_visible_fallback_results
icon_business_candidate_results
perception_benchmark_results
sam_visual_candidate_results
m29_direct/*
m29_0_x/*
m30/*
M31-M39 downstream reports
```

They may still exist in old local databases or storage directories. Current code does not delete historical developer data.
