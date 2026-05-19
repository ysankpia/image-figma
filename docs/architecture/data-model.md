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

Current M30 preview stages include:

```text
m30_queued
ocr
m29
m29_1
m29_0_2
m29_0_3
m29_0_7
m29_0_4
m29_0_5
m30_materialization
m30_asset_publish
m30_completed
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

Current roles are intentionally generic:

```text
original
m30_asset
m30_visual_asset
```

Other M30 materializer roles may be stored if a DSL asset provides a more specific role. They must still resolve to files under `/files/assets/*`.

M30 preview publishes image assets used by DSL to:

```text
storage/assets/{taskId}/m30/
/files/assets/{taskId}/m30/...
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
storage/m30_1_uploads/{taskId}/m30/m30_materialized_dsl.json
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
storage/m30_1_uploads/{taskId}/ocr/ocr.json
```

In M30 preview, OCR failure fails the task because OCR text ownership is a source fact for M29/M30 materialization.

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

SQLite does not store M29/M30 evidence payloads. They live under:

```text
storage/m30_1_uploads/{taskId}/
```

Important files:

```text
ocr/ocr.json
m29/nodes.json
m29_1/group_nodes.json
m29_0_2/text_masked_media_audit.json
m29_0_3/visual_evidence.json
m29_0_7/text_visual_ownership_gate.json
m29_0_4/visual_object_candidates.json
m29_0_5/refined_visual_objects.json
m30/m30_materialized_dsl.json
m30/m30_materialization_report.json
stage_timings.json
```

## Removed Tables

The following old result tables are no longer active source contracts:

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
```

They may still exist in old local databases. M30.2.2 does not delete them because this stage removes active source/runtime surface, not historical developer data.
