# 环境变量

后端有本地默认值，不需要 `.env` 才能启动。`.env.local` 会在默认情况下被加载；设置 `IMAGE_FIGMA_LOAD_LOCAL_ENV=false` 可关闭本地 env 文件加载。

## Current Variables

| 名称 | 用途 | 默认值 | 是否必需 |
| --- | --- | --- | --- |
| `API_BASE_URL` | 插件调用后端 API | `http://localhost:8000/api` | 否 |
| `PUBLIC_BASE_URL` | 后端生成 `/files/...` URL | `http://localhost:8000` | 否 |
| `CORS_ALLOW_ORIGINS` | 允许调用后端的 Origin，逗号分隔 | `*` | 否 |
| `STORAGE_ROOT` | 本地文件存储根目录 | `backend/storage` | 否 |
| `DATABASE_PATH` | SQLite 数据库路径 | `backend/storage/app.db` | 否 |
| `MAX_UPLOAD_BYTES` | PNG 上传大小上限 | `10485760` | 否 |
| `IMAGE_FIGMA_LOAD_LOCAL_ENV` | 是否加载仓库根目录 `.env.local` | `true` | 否 |
| `OCR_PROVIDER` | OCR provider，支持 `fake`、`baidu_ppocrv5` | `fake` | 否 |
| `OCR_MIN_CONFIDENCE` | OCR block 最低置信度 | `0.70` | 否 |
| `BAIDU_PADDLE_OCR_TOKEN` | 百度 AI Studio OCR bearer token | 无 | 仅 `OCR_PROVIDER=baidu_ppocrv5` 时需要 |
| `BAIDU_PADDLE_OCR_JOB_URL` | 百度 AI Studio OCR jobs endpoint | `https://paddleocr.aistudio-app.com/api/v2/ocr/jobs` | 否 |
| `BAIDU_PADDLE_OCR_MODEL` | 百度 OCR 模型 | `PP-OCRv5` | 否 |
| `BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS` | 百度异步 OCR 轮询间隔秒数 | `5` | 否 |
| `BAIDU_PADDLE_OCR_TIMEOUT_SECONDS` | 百度异步 OCR 单任务超时秒数 | `120` | 否 |
| `UPLOAD_PREVIEW_PROFILE` | M29 preview artifact profile，支持 `production`、`development` | `production` | 否 |
| `CODIA_UI_DETECTOR_PROVIDER` | Go Codia-like offline detector provider，支持 `openai-responses`、`openai-chat-completions` | `openai-responses` | 仅运行 `codiadetector` 时需要 |
| `CODIA_UI_DETECTOR_WIRE_API` | OpenAI-compatible wire API，支持 `responses`、`chat.completions` | `responses` | 仅运行 `codiadetector` 时需要 |
| `CODIA_UI_DETECTOR_BASE_URL` | OpenAI-compatible detector base URL，可换供应商 | `https://api.openai.com` | 仅运行 `codiadetector` 时需要 |
| `CODIA_UI_DETECTOR_API_KEY` | Go Codia-like offline detector API key | 无 | 仅运行 `codiadetector` 时需要 |
| `OPENAI_API_KEY` | `codiadetector` 的临时 fallback API key；新配置优先用 `CODIA_UI_DETECTOR_API_KEY` | 无 | 否 |
| `CODIA_UI_DETECTOR_MODEL` | Go Codia-like offline detector model id | `gpt-5.5` | 仅运行 `codiadetector` 时需要 |
| `CODIA_UI_DETECTOR_PASSES` | detector pass 列表，逗号分隔 | `layout,imageview,background,bottom_nav` | 否 |
| `CODIA_UI_DETECTOR_MAX_IMAGE_SIDE` | 每个 detector pass 发送给模型的最长边 | `1280` | 否 |
| `CODIA_UI_DETECTOR_TIMEOUT_SECONDS` | 每个 detector pass 的 provider 超时秒数 | `180` | 否 |
| `CODIA_UI_DETECTOR_TEMPERATURE` | detector 模型 temperature；`0` 表示不显式传或保持确定性配置 | `0` | 否 |
| `CODIA_SERVER_ADDR` | Go Codia Beta HTTP server 监听地址 | `127.0.0.1:8000` | 否 |
| `CODIA_SERVER_STORAGE_ROOT` | Go Codia Beta server 存储根目录 | `services/backend-go/storage/codia_server` 启动目录相对路径默认 `./storage/codia_server` | 否 |
| `CODIA_SERVER_MAX_UPLOAD_BYTES` | Go Codia Beta server PNG 上传大小上限 | `10485760` | 否 |
| `CODIA_SERVER_DETECTOR_ENABLED` | Go Codia Beta server 每次上传后是否在线调用 UI detector/VLM | `false` | 否 |
| `CODIA_SERVER_DETECTOR_CANDIDATES` | 可选 detector candidates JSON 文件，传给 Go Codia compiler | 无 | 否 |

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

OCR failure fails the current M29 preview task. The backend must not mark a task completed with fake DSL after OCR required evidence fails.

## Go Codia-like UI Detector

`CODIA_UI_DETECTOR_*` 只用于 `services/backend-go/cmd/codiadetector` 和 `codiacompile -detector-candidates` 这一条 offline / Beta side path。它不属于当前 `/api/upload-preview` 产品主链，默认不会改变现有 DSL 输出。

OpenAI-compatible Responses provider:

```bash
CODIA_UI_DETECTOR_PROVIDER=openai-responses
CODIA_UI_DETECTOR_WIRE_API=responses
CODIA_UI_DETECTOR_BASE_URL=https://api.openai.com
CODIA_UI_DETECTOR_MODEL=gpt-5.5
CODIA_UI_DETECTOR_API_KEY=...
```

OpenAI-compatible Chat Completions provider:

```bash
CODIA_UI_DETECTOR_PROVIDER=openai-chat-completions
CODIA_UI_DETECTOR_WIRE_API=chat.completions
CODIA_UI_DETECTOR_BASE_URL=https://example-provider.test
CODIA_UI_DETECTOR_MODEL=provider-model-id
CODIA_UI_DETECTOR_API_KEY=...
```

`CODIA_UI_DETECTOR_BASE_URL`、`CODIA_UI_DETECTOR_MODEL`、`CODIA_UI_DETECTOR_API_KEY` 都是供应商可替换参数，不允许写死在代码里。`codiadetector` 兼容读取 `OPENAI_API_KEY` 作为临时 fallback，但新配置应优先使用 `CODIA_UI_DETECTOR_API_KEY`，避免和历史 OpenAI vision 实验变量混在一起。

Example:

```bash
cd services/backend-go
go run ./cmd/codiadetector \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
  -out /tmp/ui-detector-018 \
  -passes layout,imageview,background,bottom_nav
```

Generation output remains report-only until explicitly passed to later permission gates:

```text
ui_detector_candidates.v1.json
ui_detector_report.md
ui_detector_overlay.png
raw_model_response/
```

## Go Codia Beta Server

`services/backend-go/cmd/codiaserver` 是插件 `Generate Beta` 路径的本地 HTTP server。它复用 `OCR_PROVIDER`，并把 PNG 交给 Go Codia compiler 输出 DSL v0.2：

```bash
cd services/backend-go
CODIA_SERVER_ADDR=127.0.0.1:8000 \
OCR_PROVIDER=baidu_ppocrv5 \
go run ./cmd/codiaserver
```

可选配置：

```bash
CODIA_SERVER_STORAGE_ROOT=./storage/codia_server
CODIA_SERVER_MAX_UPLOAD_BYTES=10485760
CODIA_SERVER_DETECTOR_ENABLED=false
CODIA_SERVER_DETECTOR_CANDIDATES=/path/to/ui_detector_candidates.v1.json
```

当 `CODIA_SERVER_DETECTOR_ENABLED=true` 且 `CODIA_SERVER_DETECTOR_CANDIDATES` 为空时，server 会在每次上传后先运行 `internal/codia/detector`，写出 `compile/detector/ui_detector_candidates.v1.json`，再把该文件传给 Go Codia compiler 的 assembly 层。detector provider、baseUrl、model、apiKey 仍由 `CODIA_UI_DETECTOR_*` 控制。

本地插件默认调用 `API_BASE_URL=http://localhost:8000/api`。如果 Python FastAPI 已占用 8000 端口，要么停止 Python server 后启动 Go `codiaserver`，要么同时修改插件 API base URL 后重新打包。

## M29 Preview Profile

```bash
UPLOAD_PREVIEW_PROFILE=production
```

`production` is the default plugin preview runtime. It keeps OCR JSON, structured M29/M29.2/M29.3/M29.4/M29.5 JSON, M29 materialized DSL/report, published renderer assets, and `stage_timings.json`. It skips raw M29 overlays and preview sheets where possible.

```bash
UPLOAD_PREVIEW_PROFILE=development
```

`development` keeps raw M29 diagnostics such as overlays and preview sheet for local evidence debugging. This variable affects only artifacts; it does not change OCR, M29 classification, replay plan, DSL schema, or Renderer behavior.

## Removed Variables

这些变量不再是 active runtime configuration。不要把它们加回 `.env.local` 期待恢复旧链路：

旧实验变量的完整示例已移动到 [legacy-env-vars.example](legacy-env-vars.example)，仅供考古和迁移排查，不是当前启动模板。

```text
LEGACY_PRE_M29_UPLOAD_ENABLED
VISUAL_PRIMITIVE_PROVIDER
DSL_PATCH_MODE
TEXT_REPLACEMENT_MODE
TEXT_BINDING_ENABLED
COMPONENT_STRUCTURE_ENABLED
COMPONENT_ANNOTATION_ENABLED
LAYER_SEPARATION_ENABLED
ASSET_SLICE_ENABLED
ICON_CANDIDATE_ENABLED
ICON_COVERAGE_AUDIT_ENABLED
ICON_GAP_CANDIDATE_ENABLED
ICON_PLACEMENT_PLAN_ENABLED
ICON_VISIBLE_FALLBACK_ENABLED
ICON_BUSINESS_CANDIDATE_ENABLED
PERCEPTION_BENCHMARK_ENABLED
SAM_VISUAL_CANDIDATE_ENABLED
OPENAI_VISION_MODEL
OCR_TEXT_EDITABILITY_ENABLED
OCR_GRAPHIC_TEXT_PRESERVE_ENABLED
OCR_TEXT_SYMBOL_LEAKAGE_CLEANUP_ENABLED
OCR_MAX_ROTATION_ANGLE
OCR_MAX_BACKGROUND_TEXTURE
OCR_MAX_BACKGROUND_COLOR_COUNT
M30_SHAPE_ERASURE_ENABLED
M30_IMAGE_ERASURE_ENABLED
M30_ACCEPTED_IMAGE_MATERIALIZATION_ENABLED
M30_ACCEPTED_IMAGE_MAX_TEXT_OVERLAP
M30_ACCEPTED_IMAGE_MIN_AREA
M30_IMAGE_ASSET_TEXT_ERASURE_ENABLED
M30_COMPOSITE_MEDIA_MATERIALIZATION_ENABLED
M30_COMPOSITE_MEDIA_MIN_AREA
M31_UPLOAD_DIAGNOSTICS_ENABLED
M31_UPLOAD_DIAGNOSTICS_STRICT
M38_HIERARCHY_MATERIALIZATION_ENABLED
M38_HIERARCHY_MATERIALIZATION_STRICT
M38_HIERARCHY_MAX_CONTAINERS
M39_CONTENT_CHROME_CLASSIFICATION_ENABLED
M39_ONNX_PROPOSER_ENABLED
M39_ONNX_MODEL_PATH
M39_1_UNIT_STRUCTURE_READINESS_ENABLED
M39_1_ONNX_UNIT_PROPOSER_ENABLED
M39_1_ONNX_MODEL_PATH
```

Historical meanings are available only in archived docs, completed plans, ADRs, and git history.
