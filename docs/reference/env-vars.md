# 环境变量

当前产品交付主线是 `apps/slice-studio`。默认本地凭证文件是：

```text
apps/slice-studio/.env.local
```

不要把 API key、bearer token、本地 storage 路径或 raw provider debug 输出提交到仓库。

旧 Pencil Python、Go Draft、Python Draft MVP、Unified Vision、Layout Advisor 等变量保留为历史/实验/显式恢复路径配置，不是当前默认运行面。

## Slice Studio Core

| 名称 | 用途 | 默认值 | 是否必需 |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_SLICE_STUDIO_API_URL` | Next.js browser client 调用 API 的 URL | `http://127.0.0.1:4110` | 否 |
| `SLICE_STUDIO_API_URL` | smoke/scripts 调用 API 的 URL | `http://127.0.0.1:4110` | 否 |
| `SLICE_STUDIO_LOAD_LOCAL_ENV` | API 是否读取 `apps/slice-studio/.env.local` | `true` | 否 |
| `SLICE_STUDIO_API_HOST` | Elysia API host | `127.0.0.1` | 否 |
| `SLICE_STUDIO_API_PORT` | Elysia API port | `4110` | 否 |
| `SLICE_STUDIO_PUBLIC_API_URL` | API 生成公开 URL 时使用 | `http://{host}:{port}` | 否 |
| `SLICE_STUDIO_STORAGE_ROOT` | Slice Studio storage 根目录 | `./storage` | 否 |
| `SLICE_STUDIO_ALLOWED_ORIGIN` | 允许的 Web origin | `http://127.0.0.1:3010` | 否 |
| `SLICE_STUDIO_MAX_UPLOAD_BYTES` | 单文件上传上限 | `20971520` | 否 |
| `SLICE_STUDIO_MAX_BATCH_UPLOAD_BYTES` | 批量上传总上限 | `314572800` | 否 |

## Slice Studio OCR And Text

| 名称 | 用途 | 默认值 | 是否必需 |
| --- | --- | --- | --- |
| `SLICE_STUDIO_OCR_PROVIDER` | Pencil export OCR provider；支持 `baidu_ppocrv5`、显式诊断 `tesseract` | `baidu_ppocrv5` | 否 |
| `SLICE_STUDIO_OCR_MIN_CONFIDENCE` | OCR line 最低置信度 | `0.70` | 否 |
| `SLICE_STUDIO_TEXT_BBOX_SOURCE` | editable text bbox 来源；`m29_ocr_hybrid` 或 `ocr` | `m29_ocr_hybrid` | 否 |
| `SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER` | text physical evidence provider；`ts_m29_physical_evidence`、`go_m29extract`、`ocr` | `ts_m29_physical_evidence` | 否 |
| `SLICE_STUDIO_M29EXTRACT_PATH` | 显式使用 Go fallback 时的 `m29extract` 路径 | `../../services/backend-go/bin/m29extract` | 仅 Go fallback 需要 |
| `BAIDU_PADDLE_OCR_TOKEN` | 百度 AI Studio OCR bearer token | 无 | 仅 `baidu_ppocrv5` 需要 |
| `BAIDU_PADDLE_OCR_JOB_URL` | 百度 AI Studio OCR jobs endpoint | `https://paddleocr.aistudio-app.com/api/v2/ocr/jobs` | 否 |
| `BAIDU_PADDLE_OCR_MODEL` | 百度 OCR 模型 | `PP-OCRv5` | 否 |
| `BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS` | OCR 轮询间隔秒数 | `5` | 否 |
| `BAIDU_PADDLE_OCR_TIMEOUT_SECONDS` | OCR 单任务超时秒数 | `120` | 否 |

OCR 是文字内容权威。M29 physical evidence 只用于更准确的文字 bbox，不创建 visible layer。默认 TS provider 不依赖 Go binary；`go_m29extract` 只作为显式 reference/fallback。

## Slice Studio AI Slice Boxes

| 名称 | 用途 | 默认值 | 是否必需 |
| --- | --- | --- | --- |
| `SLICE_STUDIO_AI_SLICE_PROVIDER` | AI 画框 provider；`openai_responses` 或 `disabled` | `openai_responses` | 否 |
| `SLICE_STUDIO_AI_SLICE_BASE_URL` | OpenAI-compatible base URL | `https://api.openai.com` | 运行 AI 画框时需要 |
| `SLICE_STUDIO_AI_SLICE_API_KEY` | AI provider API key | 无 | 运行 AI 画框时需要 |
| `SLICE_STUDIO_AI_SLICE_MODEL` | AI 画框模型 id | `gpt-5.5` | 运行 AI 画框时需要 |
| `SLICE_STUDIO_AI_SLICE_WIRE_API` | wire API；当前支持 `responses` | `responses` | 否 |
| `SLICE_STUDIO_AI_SLICE_REASONING_EFFORT` | Responses API reasoning effort | `xhigh` | 否 |
| `SLICE_STUDIO_AI_SLICE_STORE` | 是否允许 provider 存储 response | `false` | 否 |
| `SLICE_STUDIO_AI_SLICE_TIMEOUT_SECONDS` | 单 provider 请求超时秒数 | `120` | 否 |
| `SLICE_STUDIO_AI_SLICE_TRANSPORT_RETRIES` | transport retry 次数 | `2` | 否 |
| `SLICE_STUDIO_AI_SLICE_BATCH_CONCURRENCY` | 多页 AI 画框并发页数 | `4` | 否 |
| `SLICE_STUDIO_AI_SLICE_TILE_COUNT` | 单页 tile 数 | `6` | 否 |
| `SLICE_STUDIO_AI_SLICE_TILE_OVERLAP` | tile overlap 像素 | `64` | 否 |
| `SLICE_STUDIO_AI_SLICE_MAX_TILE_SIDE` | 发送给 AI 前 tile 最长边 | `1280` | 否 |
| `SLICE_STUDIO_AI_SLICE_JPEG_QUALITY` | tile JPEG quality | `75` | 否 |
| `SLICE_STUDIO_AI_SLICE_MAX_BOXES_PER_PAGE` | 单页接受框上限 | `80` | 否 |
| `SLICE_STUDIO_AI_SLICE_OVERVIEW_REVIEW` | 是否发送压缩全页 overview 做跨 tile 大资产合并 | `true` | 否 |

当前默认 prompt 策略是 `CC = Inclusive-Icons tile + Inclusive-Icons overview`。记录见 [slice-studio-ai-slice-prompt-strategies.md](slice-studio-ai-slice-prompt-strategies.md)。

## Example `.env.local`

```text
NEXT_PUBLIC_SLICE_STUDIO_API_URL=http://127.0.0.1:4110
SLICE_STUDIO_API_URL=http://127.0.0.1:4110
SLICE_STUDIO_LOAD_LOCAL_ENV=true
SLICE_STUDIO_API_PORT=4110
SLICE_STUDIO_STORAGE_ROOT=./storage
SLICE_STUDIO_ALLOWED_ORIGIN=http://127.0.0.1:3010
SLICE_STUDIO_OCR_PROVIDER=baidu_ppocrv5
SLICE_STUDIO_TEXT_BBOX_SOURCE=m29_ocr_hybrid
SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER=ts_m29_physical_evidence
SLICE_STUDIO_AI_SLICE_PROVIDER=openai_responses
SLICE_STUDIO_AI_SLICE_BASE_URL=https://api.openai.com
SLICE_STUDIO_AI_SLICE_API_KEY=
SLICE_STUDIO_AI_SLICE_MODEL=gpt-5.5
SLICE_STUDIO_AI_SLICE_BATCH_CONCURRENCY=4
BAIDU_PADDLE_OCR_TOKEN=
```

## Historical Variable Groups

Use these only when a task explicitly targets old routes.

Python Pencil assisted slice reference:

```text
PENCIL_BACKEND_ADDR
PENCIL_BACKEND_STORAGE_ROOT
PENCIL_BACKEND_M29EXTRACT
PENCIL_BACKEND_PSDLIKE_ROOT
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE
PENCIL_BACKEND_MAX_UPLOAD_BYTES
PENCIL_BACKEND_MAX_FILES
PENCIL_BACKEND_MAX_WORKERS
PENCIL_BACKEND_CORS_ALLOW_ORIGINS
OCR_PROVIDER
OCR_MIN_CONFIDENCE
```

Go Draft reference:

```text
DRAFT_SERVER_ADDR
DRAFT_SERVER_STORAGE_ROOT
DRAFT_SERVER_MAX_UPLOAD_BYTES
DRAFT_SERVER_VISION_ENABLED
VISION_PROVIDER
VISION_WIRE_API
VISION_BASE_URL
VISION_API_KEY
VISION_MODEL
VISION_DETECTOR_PASSES
VISION_DETECTOR_CONCURRENCY
VISION_MAX_IMAGE_SIDE
VISION_TIMEOUT_SECONDS
VISION_TRANSPORT_RETRIES
VISION_TEMPERATURE
VISION_STREAM
VISION_REVIEW_ENABLED
```

Other historical/experimental groups:

```text
PENCIL_ASSET_*
PENCIL_HANDOFF_*
PENCIL_SERVER_*
PIPELINE_*
OMNIPARSER_*
VLM_*
IMAGE_MIN_AREA
SHAPE_MIN_AREA
BATCH_MAX_CANDIDATES
TEXT_OVERLAP_SUPPRESS_RATIO
LAYOUT_ADVISOR_*
UNIFIED_VISION_*
```

Do not add new dependencies on historical variables for current Slice Studio work. If an old route becomes current again, first update the direction contract, code map, validation strategy, and this file.
