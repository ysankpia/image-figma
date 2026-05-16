# 可靠性

v0.1 的可靠性目标是稳定跑通主链路，而不是建设复杂平台。

## Task State

任务必须有明确状态：

- `pending`
- `uploaded`
- `processing`
- `completed`
- `failed`

任务必须有明确阶段：

- `upload`
- `preprocess`
- `ocr`
- `ai_analyze`
- `asset_crop`
- `dsl_build`
- `dsl_validate`
- `render`
- `completed`
- `failed`

## Failure Strategy

局部失败优先 fallback，不让整页失败。

M8 primitive extraction 是可观测的非关键路径：

- `fake` provider 正常情况下应 completed。
- `openai` provider 缺 key、超时、坏 JSON、空结果时，primitive result 可为 `failed` 或 `partial`。
- primitive failure 写入 `error_logs` 和 `primitive_results`。
- primitive failure 不影响 `/api/tasks/{taskId}/dsl`。

M10 OCR 和 DSL patch 也是可观测的非关键路径：

- OCR failed 时写入 `ocr_results` 和 `error_logs`。
- 百度 PP-OCRv5 token 缺失、远端失败、429、超时或 JSONL 异常时，OCR result 为 `failed`，不让上传任务失败。
- Patch failed 时写入 `dsl_patch_results` 和 `error_logs`。
- Patch validation failed 时 `/dsl` 回退 base DSL。
- Hidden text candidates 不允许破坏 fallback 视觉输出。

M13 text replacement 是可观测的非关键路径：

- 默认 `TEXT_REPLACEMENT_MODE=debug` 不改变可见 DSL。
- `TEXT_REPLACEMENT_MODE=apply` 只阻断 high-risk replacement。
- high-risk accepted replacement 会被记录为 blocked，不进入 DSL；medium-risk replacement 会记录 caution 但仍可应用。
- replacement failed/skipped 写入 `text_replacement_results` 和 `error_logs`。
- replacement validation failed 时 `/dsl` 回退 M10/M9 输出。
- fallback region 必须始终保留。

整页失败只发生在：

- PNG 无法读取。
- 后端任务不可恢复。
- DSL 无法生成或校验失败。
- Renderer 无法创建 root Frame。

## Timeout Strategy

建议目标：

- 简单页面：15 到 30 秒。
- 中等页面：30 到 60 秒。
- 复杂页面：60 到 90 秒。
- 超过 120 秒返回超时或失败提示。

## Retry Strategy

v0.1 不做复杂自动重试。

允许：

- JSON repair 最多 1 次。
- 用户手动重新上传。
- 后续可选 retry endpoint。

不允许：

- 多轮低分自动修复。
- 无限等待。
- 后台静默重跑但不更新任务状态。

## Degradation

- 图片加载失败：记录 warning，跳过或占位。
- 字体加载失败：降级默认字体。
- 图标识别不确定：fallback 图片或普通 shape。
- 复杂区域：fallback 图片。
