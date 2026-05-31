# 外部 API

当前 Draft runtime 默认只依赖本地文件系统和本地 Go backend。外部服务都是显式配置后才会调用。

## Figma Plugin API

用途：

- 创建节点。
- 设置布局和样式。
- 加载图片。
- 写入当前页面。

约束：

- 只在 Plugin Main 或 Renderer 运行环境使用。
- 后端不得依赖 Figma Plugin API。
- Plugin UI 不直接调用 Figma API。

## OCR Provider

默认：

```text
OCR_PROVIDER=fake
```

百度 PP-OCRv5：

```text
OCR_PROVIDER=baidu_ppocrv5
BAIDU_PADDLE_OCR_TOKEN=...
```

百度配置：

```text
BAIDU_PADDLE_OCR_JOB_URL=https://paddleocr.aistudio-app.com/api/v2/ocr/jobs
BAIDU_PADDLE_OCR_MODEL=PP-OCRv5
BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS=5
BAIDU_PADDLE_OCR_TIMEOUT_SECONDS=120
```

输出必须标准化为 text、bbox、confidence、lineId、blockId，并作为 M29/Draft 的文本证据。

## Vision Provider

当前 vision provider 是 OpenAI-compatible，可替换供应商。

Responses wire：

```text
VISION_PROVIDER=openai-compatible
VISION_WIRE_API=responses
VISION_BASE_URL=https://api.openai.com
VISION_MODEL=...
VISION_API_KEY=...
VISION_STREAM=false
```

Chat Completions wire：

```text
VISION_PROVIDER=openai-compatible
VISION_WIRE_API=chat.completions
VISION_BASE_URL=https://example-provider.test
VISION_MODEL=provider-model-id
VISION_API_KEY=...
```

要求：

- base URL、model、API key、wire API 必须可配置。
- 支持超时。
- 支持 bounded detector pass concurrency。
- 支持 streaming 作为 transport option。
- 输出必须标准化为 `ui_detector_candidates.v1.json` 或 `ui_candidate_review.v1.json`。
- 输出不能直接作为 Draft Runtime DSL。
- bbox 必须经过归一化和越界处理。
- 默认 vision 失败不得影响 OCR/M29 Draft fallback。

## Storage Provider

当前使用本地文件系统。

后续可接：

- OSS。
- S3 兼容对象存储。
- 签名 URL。

接远程存储前必须先更新 active plan、API contract、asset contract 和验证策略。
