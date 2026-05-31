# 环境变量

后端有本地默认值，不需要 `.env` 才能启动。`.env.local` 可用于本地凭证，但不能提交。

当前产品主线是 Go Draft backend。

## Current Variables

| 名称 | 用途 | 默认值 | 是否必需 |
| --- | --- | --- | --- |
| `API_BASE_URL` | 插件调用后端 API | `http://localhost:8000/api` | 否 |
| `PUBLIC_BASE_URL` | 后端生成本地 asset URL 时使用 | `http://localhost:8000` | 否 |
| `CORS_ALLOW_ORIGINS` | 允许调用后端的 Origin，逗号分隔 | `*` | 否 |
| `IMAGE_FIGMA_LOAD_LOCAL_ENV` | 是否加载仓库根目录 `.env.local` | `true` | 否 |
| `OCR_PROVIDER` | OCR provider，支持 `fake`、`baidu_ppocrv5` | `fake` | 否 |
| `OCR_MIN_CONFIDENCE` | OCR block 最低置信度 | `0.70` | 否 |
| `BAIDU_PADDLE_OCR_TOKEN` | 百度 AI Studio OCR bearer token | 无 | 仅 `OCR_PROVIDER=baidu_ppocrv5` 时需要 |
| `BAIDU_PADDLE_OCR_JOB_URL` | 百度 AI Studio OCR jobs endpoint | `https://paddleocr.aistudio-app.com/api/v2/ocr/jobs` | 否 |
| `BAIDU_PADDLE_OCR_MODEL` | 百度 OCR 模型 | `PP-OCRv5` | 否 |
| `BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS` | 百度异步 OCR 轮询间隔秒数 | `5` | 否 |
| `BAIDU_PADDLE_OCR_TIMEOUT_SECONDS` | 百度异步 OCR 单任务超时秒数 | `120` | 否 |
| `DRAFT_SERVER_ADDR` | Go Draft HTTP server 监听地址 | `127.0.0.1:8000` | 否 |
| `DRAFT_SERVER_STORAGE_ROOT` | Go Draft server 存储根目录 | `./storage/draft_server` | 否 |
| `DRAFT_SERVER_MAX_UPLOAD_BYTES` | Go Draft server PNG 上传大小上限 | `10485760` | 否 |
| `DRAFT_SERVER_VISION_ENABLED` | 上传后是否在线运行 vision detector/review | `false` | 否 |
| `VISION_PROVIDER` | 视觉 provider 类型 | `openai-compatible` | 仅运行 vision 时需要 |
| `VISION_WIRE_API` | OpenAI-compatible wire API，支持 `responses`、`chat.completions` | `responses` | 仅运行 vision 时需要 |
| `VISION_BASE_URL` | OpenAI-compatible base URL，可换供应商 | `https://api.openai.com` | 仅运行 vision 时需要 |
| `VISION_API_KEY` | Vision provider API key | 无 | 仅运行 vision 时需要 |
| `VISION_MODEL` | Vision model id | 无 | 仅运行 vision 时需要 |
| `VISION_DETECTOR_PASSES` | detector pass 列表，逗号分隔 | `layout,imageview,background,bottom_nav` | 否 |
| `VISION_DETECTOR_CONCURRENCY` | detector pass 并发数 | `3` | 否 |
| `VISION_MAX_IMAGE_SIDE` | 每个 detector pass 发送给模型的最长边 | `1280` | 否 |
| `VISION_TIMEOUT_SECONDS` | 每个 provider 请求超时秒数 | `90` | 否 |
| `VISION_TEMPERATURE` | 模型 temperature；`0` 表示确定性/不显式传 | `0` | 否 |
| `VISION_STREAM` | 是否请求 streaming/SSE 响应 | `false` | 否 |
| `VISION_REVIEW_ENABLED` | 是否运行二次 review/reconciliation | `false` | 否 |

## Draft Server

Local run:

```bash
cd services/backend-go
DRAFT_SERVER_ADDR=127.0.0.1:8000 \
OCR_PROVIDER=baidu_ppocrv5 \
go run ./cmd/draftserver
```

The plugin should call:

```text
API_BASE_URL=http://localhost:8000/api
```

Draft endpoints:

```text
POST /api/draft-preview
GET /api/draft-preview/{taskId}
GET /api/draft-preview/{taskId}/dsl
GET /api/draft-preview/{taskId}/assets/{assetId}.png
```

## Vision Provider

OpenAI-compatible Responses:

```bash
VISION_PROVIDER=openai-compatible
VISION_WIRE_API=responses
VISION_BASE_URL=https://api.openai.com
VISION_MODEL=...
VISION_API_KEY=...
VISION_STREAM=false
VISION_DETECTOR_CONCURRENCY=3
```

OpenAI-compatible Chat Completions:

```bash
VISION_PROVIDER=openai-compatible
VISION_WIRE_API=chat.completions
VISION_BASE_URL=https://example-provider.test
VISION_MODEL=provider-model-id
VISION_API_KEY=...
```

`VISION_BASE_URL`、`VISION_MODEL`、`VISION_API_KEY`、`VISION_WIRE_API` 都是供应商可替换参数，不允许写死在代码里。

Vision 是可选证据源。默认情况下，provider TLS、超时、5xx、空响应或 JSON 解析失败不应阻塞 M29/OCR Draft fallback，除非请求显式要求 vision。

## OCR

Default local provider:

```bash
OCR_PROVIDER=fake
```

Baidu PP-OCRv5 async provider:

```bash
OCR_PROVIDER=baidu_ppocrv5
BAIDU_PADDLE_OCR_TOKEN=...
```

`BAIDU_PADDLE_OCR_TOKEN` must be supplied through local environment or an untracked env file. Do not commit real tokens.

## Legacy Variables

旧 Codia Beta 变量不再是当前产品 runtime 配置。不要在新代码中新增对这些变量的依赖：

```text
CODIA_UI_DETECTOR_PROVIDER
CODIA_UI_DETECTOR_WIRE_API
CODIA_UI_DETECTOR_BASE_URL
CODIA_UI_DETECTOR_API_KEY
CODIA_UI_DETECTOR_MODEL
CODIA_UI_DETECTOR_PASSES
CODIA_UI_DETECTOR_STREAM
CODIA_SERVER_ADDR
CODIA_SERVER_STORAGE_ROOT
CODIA_SERVER_DETECTOR_ENABLED
CODIA_SERVER_DETECTOR_CANDIDATES
```

旧实验变量完整示例保留在 [legacy-env-vars.example](legacy-env-vars.example)，仅供考古和迁移排查。
