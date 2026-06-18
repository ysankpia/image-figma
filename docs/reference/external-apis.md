# 外部 API

当前 Slice Studio 默认依赖本地文件系统、本地 Elysia API、SQLite、Sharp。外部服务只有在显式配置后才会调用。

## Slice Studio OCR Provider

默认 OCR provider：

```text
SLICE_STUDIO_OCR_PROVIDER=baidu_ppocrv5
```

百度 PP-OCRv5：

```text
BAIDU_PADDLE_OCR_TOKEN=...
BAIDU_PADDLE_OCR_JOB_URL=https://paddleocr.aistudio-app.com/api/v2/ocr/jobs
BAIDU_PADDLE_OCR_MODEL=PP-OCRv5
BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS=5
BAIDU_PADDLE_OCR_TIMEOUT_SECONDS=120
```

输出必须标准化为 text、bbox、confidence、lineId/blockId 等内部结构。OCR 是文字内容证据，不拥有最终 visible asset。

## Slice Studio AI Slice Provider

当前 AI 画框使用 OpenAI-compatible Responses API：

```text
SLICE_STUDIO_AI_SLICE_PROVIDER=openai_responses
SLICE_STUDIO_AI_SLICE_BASE_URL=https://api.openai.com
SLICE_STUDIO_AI_SLICE_MODEL=...
SLICE_STUDIO_AI_SLICE_API_KEY=...
SLICE_STUDIO_AI_SLICE_WIRE_API=responses
SLICE_STUDIO_AI_SLICE_REASONING_EFFORT=xhigh
SLICE_STUDIO_AI_SLICE_STORE=false
```

要求：

- base URL、model、API key、wire API 必须可配置；
- 图片必须先切 tile 并压缩；
- provider 请求必须有 timeout 和 retry；
- 输出必须解析成 bbox 候选并做 clamp/filter/dedupe；
- AI boxes 不写数据库，只有前端保存后才成为普通 SliceRecord。

## Figma Plugin API

Figma Plugin API 属于历史/延后 Draft plugin route。当前 Slice Studio handoff 通过 `project.zip/design.pen`，不直接调用 Figma Plugin API。

历史插件边界：

- Plugin Main 可调用 Figma Plugin API。
- Renderer receives DSL and adapter methods。
- Backend 不调用 Figma Plugin API。
- Plugin UI iframe 不直接调用 Figma API。

## Historical XPay / 易支付 Payment Candidate

XPay / 易支付 was reviewed as an early-launch payment candidate, but plan 196 removed payment, entitlement, billing, and admin code from the current runtime:

```text
https://x.yhhrun.cn/doc/epay_submit
```

Do not wire this provider into the current product without a new active plan. If payment returns later, use it only behind Slice Studio's own server-side order and fulfillment contract. The provider may collect money and call back, but Slice Studio must own:

- local payment order creation;
- webhook signature verification;
- amount and order id validation;
- idempotent entitlement fulfillment;
- usage/credit/subscription state;
- raw payment event logging;
- admin repair and audit trail.

Detailed notes: [payment-provider-xpay.md](payment-provider-xpay.md).

## Historical Vision Provider

旧 Go Draft vision provider 使用 `VISION_*` 变量。它是 deferred runtime 配置，不是当前 Slice Studio AI 画框配置：

```text
VISION_PROVIDER
VISION_WIRE_API
VISION_BASE_URL
VISION_MODEL
VISION_API_KEY
VISION_DETECTOR_CONCURRENCY
VISION_TIMEOUT_SECONDS
VISION_REVIEW_ENABLED
```

历史 vision 输出不能直接作为 Draft Runtime DSL，也不能接到当前 Slice Studio export truth source。

## Storage Provider

当前使用本地文件系统和 SQLite。

后续可接：

- OSS；
- S3 兼容对象存储；
- 签名 URL。

接远程存储前必须先更新 active plan、API contract、asset contract、env vars、security docs 和验证策略。
