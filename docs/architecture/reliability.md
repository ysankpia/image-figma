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
