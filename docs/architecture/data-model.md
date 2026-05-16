# 数据模型

v0.1 使用 SQLite 记录任务、资产、DSL 结果和调试信息。

## Tables

建议表：

- `tasks`
- `assets`
- `dsl_results`
- `error_logs`
- `model_call_logs`

可选表：

- `render_logs`

## tasks

用途：记录上传和处理任务。

核心字段：

- `id`
- `status`
- `stage`
- `original_filename`
- `mime_type`
- `file_size`
- `width`
- `height`
- `upload_path`
- `quality_flags`
- `created_at`
- `updated_at`
- `completed_at`
- `failed_at`

`status` 枚举：

- `pending`
- `uploaded`
- `processing`
- `completed`
- `failed`

## assets

用途：记录原图、裁切图、fallback、头像、商品图、Banner 等资产。

核心字段：

- `id`
- `task_id`
- `role`
- `path`
- `url`
- `mime_type`
- `width`
- `height`
- `source_bbox`
- `created_at`

常见 `role`：

- `original`
- `original_reference`
- `image`
- `avatar`
- `product`
- `banner`
- `fallback`
- `icon`

## dsl_results

用途：记录 DSL 结果文件和校验状态。

核心字段：

- `id`
- `task_id`
- `dsl_path`
- `version`
- `validation_status`
- `validation_errors`
- `created_at`

`validation_status`：

- `valid`
- `repaired`
- `invalid`

## error_logs

用途：记录任务失败和可追踪错误。

核心字段：

- `id`
- `task_id`
- `stage`
- `error_code`
- `message`
- `detail`
- `severity`
- `created_at`

## model_call_logs

用途：记录 OCR/AI 调用摘要，不默认保存完整模型输入输出。

核心字段：

- `id`
- `task_id`
- `stage`
- `model`
- `status`
- `input_summary`
- `output_summary`
- `latency_ms`
- `created_at`

## Explicit Non-Models

v0.1 不建：

- users。
- organizations。
- teams。
- billing。
- quota。
- permissions。
- full history。
- quality score dashboard。

这些表会制造假的产品复杂度。
