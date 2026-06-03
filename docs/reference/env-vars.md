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
| `PENCIL_BACKEND_ADDR` | Python Pencil project server 监听地址 | `127.0.0.1:8100` | 否 |
| `PENCIL_BACKEND_STORAGE_ROOT` | Python Pencil project server 存储根目录 | `./storage` | 否 |
| `PENCIL_BACKEND_M29EXTRACT` | 本地 `m29extract` 可执行文件路径 | 自动查找 `m29extract`/`../backend-go/bin/m29extract` | 部署时建议显式配置 |
| `PENCIL_BACKEND_PSDLIKE_ROOT` | PSD-like Python 服务目录；`boundarySource=psdlike` 或 `hybrid` 时作为子进程运行 | 自动查找 `services/psdlike-python` | `boundarySource=psdlike/hybrid` 且默认路径不存在时需要 |
| `PENCIL_BACKEND_PSDLIKE_TILE_SIZE` | PSD-like tile map 尺寸 | `8` | 否 |
| `PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE` | Python Pencil project server 在请求/CLI 未显式指定 `boundarySource` 时使用的边界源 | `psdlike` | 否 |
| `PENCIL_BACKEND_MAX_UPLOAD_BYTES` | Python Pencil project server 单图片上传大小上限 | `10485760` | 否 |
| `PENCIL_BACKEND_MAX_FILES` | Python Pencil project server 单项目最大图片数 | `20` | 否 |
| `PENCIL_BACKEND_MAX_WORKERS` | Python Pencil project server 后台导出并发数；部署低内存机器建议保持 `1` | `1` | 否 |
| `PENCIL_BACKEND_CORS_ALLOW_ORIGINS` | Python Pencil project server CORS origins，逗号分隔 | `*` | 否 |
| `PENCIL_SERVER_ADDR` | Go Pencil project server 监听地址，已被 Python Pencil backend 取代 | `127.0.0.1:8100` | legacy |
| `PENCIL_SERVER_STORAGE_ROOT` | Go Pencil project server 存储根目录，已被 Python Pencil backend 取代 | `./storage/pencil_server` | legacy |
| `PENCIL_SERVER_MAX_UPLOAD_BYTES` | Go Pencil project server 单 PNG 上传大小上限，已被 Python Pencil backend 取代 | `10485760` | legacy |
| `PENCIL_SERVER_MAX_FILES` | Go Pencil project server 单项目最大 PNG 数，已被 Python Pencil backend 取代 | `20` | legacy |
| `VISION_PROVIDER` | 视觉 provider 类型 | `openai-compatible` | 仅运行 vision 时需要 |
| `VISION_WIRE_API` | OpenAI-compatible wire API，支持 `responses`、`chat.completions` | `responses` | 仅运行 vision 时需要 |
| `VISION_BASE_URL` | OpenAI-compatible base URL，可换供应商 | `https://api.openai.com` | 仅运行 vision 时需要 |
| `VISION_API_KEY` | Vision provider API key | 无 | 仅运行 vision 时需要 |
| `VISION_MODEL` | Vision model id | 无 | 仅运行 vision 时需要 |
| `VISION_DETECTOR_PASSES` | detector pass 列表，逗号分隔 | `layout,imageview,background,bottom_nav` | 否 |
| `VISION_DETECTOR_CONCURRENCY` | detector pass 并发数 | `3` | 否 |
| `VISION_MAX_IMAGE_SIDE` | 每个 detector pass 发送给模型的最长边 | `1280` | 否 |
| `VISION_TIMEOUT_SECONDS` | 每个 provider 请求超时秒数 | `90` | 否 |
| `VISION_TRANSPORT_RETRIES` | Python OmniParser/VLM candidate classifier 的 provider transport retry 次数 | `3` | 否 |
| `VISION_TEMPERATURE` | 模型 temperature；`0` 表示确定性/不显式传 | `0` | 否 |
| `VISION_STREAM` | 是否请求 streaming/SSE 响应 | `false` | 否 |
| `VISION_REVIEW_ENABLED` | 是否运行二次 review/reconciliation | `false` | 否 |
| `PIPELINE_SERVER_PORT` | Python Draft MVP server 端口 | `8001` | 否 |
| `PIPELINE_STORAGE_ROOT` | Python Draft MVP storage 根目录 | `./storage` | 否 |
| `PIPELINE_MAX_UPLOAD_BYTES` | Python Draft MVP PNG 上传大小上限 | `20971520` | 否 |
| `OMNIPARSER_MODEL_PATH` | OmniParser 6MB ONNX 模型路径 | `/Volumes/WorkDrive/Models/model_fp16.onnx` | 运行 Python OmniParser 时需要 |
| `OMNIPARSER_CONFIDENCE` | OmniParser objectness 最低置信度 | `0.3` | 否 |
| `OMNIPARSER_NMS_IOU` | OmniParser NMS IoU 阈值 | `0.5` | 否 |
| `OMNIPARSER_INPUT_SIZE` | OmniParser letterbox 输入尺寸 | `640` | 否 |
| `VLM_MIN_CONFIDENCE` | Python VLM candidate classification 最低置信度 | `0.65` | 否 |
| `IMAGE_MIN_AREA` | Python planner image layer 最小面积 | `400` | 否 |
| `SHAPE_MIN_AREA` | Python planner shape layer 最小面积 | `1200` | 否 |
| `BATCH_MAX_CANDIDATES` | Python VLM candidate batch hard cap | `25` | 否 |
| `TEXT_OVERLAP_SUPPRESS_RATIO` | Python planner image 候选允许的最大 OCR overlap 比例 | `0.08` | 否 |
| `LAYOUT_ADVISOR_WIRE_API` | Layout advisor 实验使用的 OpenAI-compatible wire API，支持 `responses`、`chat.completions` | `responses` | 仅运行 advisor 实验时需要 |
| `LAYOUT_ADVISOR_BASE_URL` | Layout advisor 实验 provider base URL | `https://api.openai.com` | 仅运行 advisor 实验时需要 |
| `LAYOUT_ADVISOR_API_KEY` | Layout advisor 实验 API key | 无 | 仅运行 advisor 实验时需要 |
| `LAYOUT_ADVISOR_MODEL` | Layout advisor 实验模型 id | 无 | 仅运行 advisor 实验时需要 |
| `LAYOUT_ADVISOR_TIMEOUT_SECONDS` | Layout advisor provider 请求超时秒数 | `120` | 否 |
| `LAYOUT_ADVISOR_TEMPERATURE` | Layout advisor temperature；默认固定确定性 | `0` | 否 |
| `UNIFIED_VISION_ENABLED` | 是否运行 Unified Vision layout 实验；只输出并列 artifact，不覆盖 baseline | `false` | 否 |
| `UNIFIED_VISION_PROVIDER` | Unified Vision provider 类型 | `openai-compatible` | 仅运行 unified 实验时需要 |
| `UNIFIED_VISION_WIRE_API` | OpenAI-compatible wire API，支持 `responses`、`chat.completions` | `responses` | 仅运行 unified 实验时需要 |
| `UNIFIED_VISION_BASE_URL` | Unified Vision provider base URL | `https://api.openai.com` | 仅运行 unified 实验时需要 |
| `UNIFIED_VISION_API_KEY` | Unified Vision provider API key | 无 | 仅运行 unified 实验时需要 |
| `UNIFIED_VISION_MODEL` | Unified Vision 模型 id | 无 | 仅运行 unified 实验时需要 |
| `UNIFIED_VISION_CONCURRENCY` | Unified Vision batch 并发请求数 | `3` | 否 |
| `UNIFIED_VISION_TIMEOUT_SECONDS` | Unified Vision 单 batch provider 超时秒数 | `180` | 否 |
| `UNIFIED_VISION_TEMPERATURE` | Unified Vision temperature；默认确定性 | `0` | 否 |
| `UNIFIED_VISION_TRANSPORT_RETRIES` | HTTP/断连/限流等 transport retry 次数 | `3` | 否 |
| `UNIFIED_VISION_REPAIR_ATTEMPTS` | validator 拒绝后的 semantic repair 次数 | `1` | 否 |
| `UNIFIED_VISION_MAX_ITEMS_PER_BATCH` | 复杂度分批后的 soft item cap | `30` | 否 |
| `UNIFIED_VISION_HARD_MAX_ITEMS_PER_BATCH` | provider 保护 hard item cap | `45` | 否 |
| `UNIFIED_VISION_MAX_COMPLEXITY` | batch 复杂度上限，超过会继续拆分 | `110` | 否 |
| `UNIFIED_VISION_MIN_CONFIDENCE` | accepted group 最低 confidence | `0.70` | 否 |
| `UNIFIED_VISION_MAX_FIT_RATIO` | accepted group 最大 required-size/union-size ratio | `1.01` | 否 |
| `UNIFIED_VISION_MAX_Y_SPREAD_FACTOR` | cross-axis spread 相对 median cross size 的上限 | `1.60` | 否 |
| `UNIFIED_VISION_MAX_GAP` | accepted group 最大 expected/actual gap | `96` | 否 |
| `UNIFIED_VISION_MAX_GAP_VARIANCE` | accepted group 最大 gap variance | `4096` | 否 |
| `UNIFIED_VISION_CROP_PADDING` | section/batch crop padding 像素 | `10` | 否 |

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

## Pencil Python Project Server

Current Pencil delivery route:

```bash
cd services/pencil-python-backend
PENCIL_BACKEND_M29EXTRACT=../backend-go/bin/m29extract \
PENCIL_BACKEND_PSDLIKE_ROOT=../psdlike-python \
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike \
PENCIL_BACKEND_ADDR=127.0.0.1:8100 \
PENCIL_BACKEND_MAX_WORKERS=1 \
OCR_PROVIDER=baidu_ppocrv5 \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
```

Pencil project endpoints:

```text
POST /api/pencil/projects
GET /api/pencil/projects/{taskId}
GET /api/pencil/projects/{taskId}/manifest
GET /api/pencil/projects/{taskId}/download.zip
```

The project server returns a downloadable ZIP containing `clean-editable`, `visual-fidelity`, and `visual-ocr` `.pen` packages when `mode=all`.

For lower-fragment Pencil assets, the default Pencil boundary source is `psdlike`. Override it with `PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=m29|psdlike|hybrid`, send `boundarySource` in `POST /api/pencil/projects`, or use CLI `--boundary-source ...`. If PSD-like misses small local objects, use `boundarySource=hybrid`; it keeps PSD-like as the primary boundary source and uses M29 only for low-coverage fallback objects.

For repeatable offline audits, run PSD-like batch first and then reuse those artifacts from the Pencil CLI:

```bash
cd services/pencil-python-backend
uv run python -m app.cli.export_project \
  --manifest /Volumes/WorkDrive/pencil-exports/psdlike-batch/input_manifest.v1.json \
  --out /Volumes/WorkDrive/pencil-exports/pencil-from-psdlike-batch \
  --project-name "Pencil From PSD-like Batch" \
  --mode all \
  --columns auto \
  --boundary-source psdlike \
  --psdlike-artifacts-root /Volumes/WorkDrive/pencil-exports/psdlike-batch \
  --include-debug
```

`--psdlike-artifacts-root` is a CLI/local workflow parameter, not an HTTP upload parameter, because it points at a server-local directory.

`m29extract` should be built from the Go backend and used as a local executable:

```bash
cd services/backend-go
mkdir -p bin
go build -o bin/m29extract ./cmd/m29extract
```

## Legacy Go Pencil Project Server

Local run:

```bash
cd services/pencil-go
PENCIL_SERVER_ADDR=127.0.0.1:8100 \
OCR_PROVIDER=baidu_ppocrv5 \
go run ./cmd/pencilserver
```

Pencil project endpoints:

```text
POST /api/pencil/projects
GET /api/pencil/projects/{taskId}
GET /api/pencil/projects/{taskId}/manifest
GET /api/pencil/projects/{taskId}/download.zip
```

This Go Pencil server is retained as a superseded experiment. Do not use it as the current product delivery route.

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

## Backend Python OmniParser Draft MVP

Python Draft MVP 使用 `OCR + OmniParser + VLM candidate classifier + deterministic planner`。这里的 VLM 只分类 OmniParser 候选框，不生成 bbox、文字、HTML、CSS、Figma 或最终 DSL。

```bash
cd services/backend-python
PIPELINE_SERVER_PORT=8001
OMNIPARSER_MODEL_PATH=/Volumes/WorkDrive/Models/model_fp16.onnx
VISION_BASE_URL=https://aicode.cat
VISION_MODEL=gpt-5.5
VISION_API_KEY=...
VLM_MIN_CONFIDENCE=0.65
IMAGE_MIN_AREA=400
SHAPE_MIN_AREA=1200
BATCH_MAX_CANDIDATES=25
TEXT_OVERLAP_SUPPRESS_RATIO=0.08
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

This path does not use M29 and must not read Codia golden data at runtime. OCR remains the text authority; OmniParser remains the bbox candidate source; VLM remains a classifier only.

## Layout Advisor Experiment

Layout advisor 是 `cmd/layoutcompile` 的离线 A/B 实验，不是 Draft runtime，也不替代 Python 历史 `/api/upload-preview`。它只请求模型给出 evidence 分组建议，不能生成 HTML、Figma、文字、bbox 或 asset。

```bash
LAYOUT_ADVISOR_WIRE_API=responses
LAYOUT_ADVISOR_BASE_URL=https://api.openai.com
LAYOUT_ADVISOR_MODEL=...
LAYOUT_ADVISOR_API_KEY=...
LAYOUT_ADVISOR_TIMEOUT_SECONDS=120
LAYOUT_ADVISOR_TEMPERATURE=0
```

`LAYOUT_ADVISOR_*` 必须和 `VISION_*` 分开配置：`VISION_*` 是单元素候选/语义标签，`LAYOUT_ADVISOR_*` 是关系分组建议。两者都不得成为 OCR text、M29 bbox 或 asset 的最终权威。

## Unified Vision Experiment

Unified Vision 是 `cmd/layoutcompile -unified-vision` 的离线结构实验，不是 Draft runtime 默认路径。它按 section/batch 发送裁切图和 flow evidence，请模型提出 flat grouping + text style 建议，然后由 Go validator 决定 accepted/rejected/fallback。baseline `ui_layout_ir.v1.json` 不会被覆盖。

```bash
UNIFIED_VISION_ENABLED=false
UNIFIED_VISION_WIRE_API=responses
UNIFIED_VISION_BASE_URL=https://api.openai.com
UNIFIED_VISION_MODEL=...
UNIFIED_VISION_API_KEY=...
UNIFIED_VISION_CONCURRENCY=3
UNIFIED_VISION_TRANSPORT_RETRIES=3
UNIFIED_VISION_REPAIR_ATTEMPTS=1
UNIFIED_VISION_MAX_ITEMS_PER_BATCH=30
UNIFIED_VISION_HARD_MAX_ITEMS_PER_BATCH=45
UNIFIED_VISION_MAX_COMPLEXITY=110
UNIFIED_VISION_MAX_FIT_RATIO=1.01
```

`UNIFIED_VISION_*` 不复用 `VISION_*`：`VISION_*` 是单元素候选检测，`UNIFIED_VISION_*` 是关系分组实验。模型不能成为 OCR text、M29 bbox、asset crop、materialize 分类或最终 Figma tree 的权威。

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
