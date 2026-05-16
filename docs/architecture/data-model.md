# 数据模型

v0.1 使用 SQLite 记录任务、资产、DSL 结果和调试信息。

## Tables

当前已实现表：

- `tasks`
- `assets`
- `dsl_results`
- `error_logs`

后续建议表：

- `model_call_logs`

可选表：

- `render_logs`

## tasks

用途：记录上传和处理任务。

核心字段：

- `id`
- `status`
- `stage`
- `progress`
- `message`
- `original_filename`
- `mime_type`
- `file_size`
- `upload_path`
- `created_at`
- `updated_at`
- `completed_at`
- `failed_at`

`status` 枚举：

- `completed`
- `failed`

M7 只写入 `completed`。后续接真实处理管线再补 `pending`、`uploaded`、`processing`。

## assets

用途：记录原图、裁切图、fallback、头像、商品图、Banner 等资产。

核心字段：

- `id`
- `asset_id`
- `task_id`
- `role`
- `path`
- `url`
- `mime_type`
- `width`
- `height`
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

M7 写入真实 PNG 宽高到 `assets.width` 和 `assets.height`。

当前上传成功路径会写入：

- `asset_original`：原始上传 PNG。
- `asset_banner`：兼容旧查询的 full-image fallback 资产，M7 成功切分时不进入 DSL。
- `asset_region_header`：顶部 region crop。
- `asset_region_content`：中部 region crop。
- `asset_region_bottom`：底部 region crop。

如果 cropper 不支持该 PNG 格式，DSL 只使用 `asset_original` 和 `asset_banner`，并在 `meta.qualityFlags` 标记 `region_crop_unsupported`。

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

用途：记录 OCR/AI 调用摘要，不默认保存完整模型输入输出。M7 不创建该表，因为没有模型调用。

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
