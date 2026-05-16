# 数据模型

v0.1 使用 SQLite 记录任务、资产、DSL 结果和调试信息。

## Tables

当前已实现表：

- `tasks`
- `assets`
- `dsl_results`
- `error_logs`
- `primitive_results`
- `ocr_results`
- `dsl_patch_results`
- `text_replacement_results`

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

M13 只写入 `completed`。后续接真实处理管线再补 `pending`、`uploaded`、`processing`。

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

M9 写入真实 PNG 宽高到 `assets.width` 和 `assets.height`。

当前上传成功路径会写入：

- `asset_original`：原始上传 PNG。
- `asset_banner`：兼容旧查询的 full-image fallback 资产，M9 成功切分时不进入 DSL。
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

## primitive_results

用途：记录 M8 visual primitive candidate 文件和 provider 状态。

核心字段：

- `id`
- `task_id`
- `provider`
- `model`
- `status`
- `primitive_path`
- `primitive_count`
- `relation_count`
- `error_code`
- `error_message`
- `created_at`

`status`：

- `completed`
- `partial`
- `failed`
- `skipped`

primitive payload 本体写入 `backend/storage/primitives/{taskId}.json`，SQLite 只保存索引和摘要，避免大 JSON 塞进数据库。

primitive extraction 失败时仍写入一条 `primitive_results`，`status` 为 `failed`，并在 `error_logs` 记录 `primitive_extract` 阶段错误。这样上传主链路能继续返回 DSL，同时调试端能看到失败原因。

## ocr_results

用途：记录 M9 OCR candidate 文件和 provider 状态。

核心字段：

- `id`
- `task_id`
- `provider`
- `model`
- `status`
- `ocr_path`
- `block_count`
- `error_code`
- `error_message`
- `created_at`

OCR payload 本体写入 `backend/storage/ocr/{taskId}.json`。

## dsl_patch_results

用途：记录 M9 DSL patch 文件、模式和状态。

核心字段：

- `id`
- `task_id`
- `mode`
- `status`
- `patch_path`
- `patch_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Patch payload 本体写入 `backend/storage/patches/{taskId}.json`。

## text_replacement_results

用途：记录 M13 visible text replacement 文件、模式和状态。

核心字段：

- `id`
- `task_id`
- `mode`
- `status`
- `replacement_path`
- `accepted_count`
- `rejected_count`
- `warning_count`
- `error_code`
- `error_message`
- `created_at`

Replacement payload 本体写入 `backend/storage/text_replacements/{taskId}.json`。默认 `debug` 只保存 accepted/rejected decisions 和 quality/application 报告；`apply` 把非 high-risk 的 accepted replacement 合并进最终 DSL。SQLite 不单独保存 applied/blocked 计数，这些统计写在 JSON `meta` 中。

## model_call_logs

用途：记录 OCR/AI 调用摘要，不默认保存完整模型输入输出。M9 不创建该表；OpenAI provider 当前只把 primitive extraction 的结果摘要写入 `primitive_results`，失败细节写入 `error_logs`。

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
