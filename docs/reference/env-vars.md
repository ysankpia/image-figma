# 环境变量

当前产品交付主线在仓库根目录。默认本地凭证文件是：

```text
.env.local
```

不要把 API key、bearer token、本地 storage 路径或 raw provider debug 输出提交到仓库。

旧 Pencil Python、Go Draft、Python Draft MVP、Unified Vision、Layout Advisor 等变量保留为历史/实验/显式恢复路径配置，不是当前默认运行面。

## Slice Studio Core

| 名称 | 用途 | 默认值 | 是否必需 |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_SLICE_STUDIO_API_URL` | 浏览器 API URL 覆盖；为空时使用 Next 同源 `/api` rewrite | 空 | 否 |
| `SLICE_STUDIO_API_URL` | Next rewrite、server pages、smoke/scripts 调用 Elysia API 的 URL | `http://127.0.0.1:4110` | 否 |
| `SLICE_STUDIO_LOAD_LOCAL_ENV` | API 是否读取根目录 `.env.local` | `true` | 否 |
| `SLICE_STUDIO_API_HOST` | Elysia API host | `127.0.0.1` | 否 |
| `SLICE_STUDIO_API_PORT` | Elysia API port | `4110` | 否 |
| `SLICE_STUDIO_PUBLIC_API_URL` | API 生成公开 URL 时使用 | `http://{host}:{port}` | 否 |
| `SLICE_STUDIO_AUTH_COOKIE_NAME` | 会话 cookie 名 | `slice_studio_session` | 否 |
| `SLICE_STUDIO_AUTH_SESSION_TTL_DAYS` | 会话有效天数 | `30` | 否 |
| `SLICE_STUDIO_AUTH_SECURE_COOKIES` | 是否给会话 cookie 加 Secure | 生产默认 `true`，本地默认 `false` | 否 |
| `SLICE_STUDIO_DOWNLOAD_SIGNING_SECRET` | 本地/生产下载签名密钥；用于签发 `/api/storage-download` token | 回退到 `SLICE_STUDIO_LOCAL_OWNER_PASSWORD`，再回退到内置开发默认值 | 否 |
| `SLICE_STUDIO_DOWNLOAD_URL_TTL_SECONDS` | 下载 token 有效秒数 | `600` | 否 |
| `SLICE_STUDIO_LOCAL_OWNER_EMAIL` | 本地/bootstrap owner 邮箱 | `local@slicestudio.dev` | 否 |
| `SLICE_STUDIO_LOCAL_OWNER_NAME` | 本地/bootstrap owner 昵称 | `Local Owner` | 否 |
| `SLICE_STUDIO_LOCAL_OWNER_PASSWORD` | 本地/bootstrap owner 密码；生产必须覆盖 | `slice-studio-local-owner` | 否 |
| `SLICE_STUDIO_STORAGE_ROOT` | Slice Studio storage 根目录 | `./storage` | 否 |
| `SLICE_STUDIO_DATABASE_PROVIDER` | 数据库 provider；`sqlite` 或 `postgres`。为空时有 `SLICE_STUDIO_DATABASE_URL` 自动视为 `postgres`，否则为 `sqlite` | `sqlite` | 否 |
| `SLICE_STUDIO_DATABASE_URL` | Postgres 连接串；只在 Postgres provider 下使用 | 空 | Postgres 需要 |
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
| `SLICE_STUDIO_M29EXTRACT_PATH` | 显式使用 Go fallback 时的 `m29extract` 路径 | `archive/legacy-code/services/backend-go/bin/m29extract` | 仅 Go fallback 需要 |
| `SLICE_STUDIO_TEXT_STYLE_PROVIDER` | editable text style provider；`psdlike` 或 `fallback` | 正常运行 `psdlike`，测试环境 `fallback` | 否 |
| `SLICE_STUDIO_TEXT_STYLE_BASE_URL` | PSD-like text-style service base URL | `http://127.0.0.1:4120` | 使用 `psdlike` 时需要 |
| `SLICE_STUDIO_TEXT_STYLE_TIMEOUT_SECONDS` | text-style service 单页 batch 超时秒数 | `8` | 否 |
| `BAIDU_PADDLE_OCR_TOKEN` | 百度 AI Studio OCR bearer token | 无 | 仅 `baidu_ppocrv5` 需要 |
| `BAIDU_PADDLE_OCR_JOB_URL` | 百度 AI Studio OCR jobs endpoint | `https://paddleocr.aistudio-app.com/api/v2/ocr/jobs` | 否 |
| `BAIDU_PADDLE_OCR_MODEL` | 百度 OCR 模型 | `PP-OCRv5` | 否 |
| `BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS` | OCR 轮询间隔秒数 | `5` | 否 |
| `BAIDU_PADDLE_OCR_TIMEOUT_SECONDS` | OCR 单任务超时秒数 | `120` | 否 |

OCR 是文字内容权威。M29 physical evidence 只用于更准确的文字 bbox，不创建 visible layer。默认 TS provider 不依赖 Go binary；`go_m29extract` 只作为显式 reference/fallback。PSD-like text-style service 只测量 editable text 的字体大小、字重、颜色和对齐；它不决定文字是否可编辑、不决定 slice ownership、不生成 Pencil 图层。服务不可用时导出回落到 TS 本地估算并继续完成。

## Slice Studio AI Slice Boxes

| 名称 | 用途 | 默认值 | 是否必需 |
| --- | --- | --- | --- |
| `SLICE_STUDIO_AI_SLICE_PROVIDER` | AI 画框 provider；`openai_responses` 或 `disabled` | `openai_responses` | 否 |
| `SLICE_STUDIO_AI_SLICE_BASE_URL` | OpenAI-compatible base URL | `https://api.openai.com` | 运行 AI 画框时需要 |
| `SLICE_STUDIO_AI_SLICE_API_KEY` | AI provider API key | 无 | 运行 AI 画框时需要 |
| `SLICE_STUDIO_AI_SLICE_MODEL` | AI 画框模型 id | `gpt-5.5` | 运行 AI 画框时需要 |
| `SLICE_STUDIO_AI_SLICE_WIRE_API` | wire API；支持 `responses`、`chat_completions` | `responses` | 否 |
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
| `SLICE_STUDIO_AI_SLICE_YOLO_MODEL_PATH` | 本地 YOLO provider 权重路径 | 空 | 使用 `yolo_local` 时需要 |
| `SLICE_STUDIO_AI_SLICE_YOLO_CLASSES` | 本地 YOLO provider 允许进入候选的类别 CSV | `Image,BackgroundImage,Map,Icon,Modal,Drawer` | 否 |
| `SLICE_STUDIO_AI_SLICE_YOLO_CONFIDENCE` | 本地 YOLO provider 置信度阈值 | `0.35` | 否 |
| `SLICE_STUDIO_AI_SLICE_YOLO_IMAGE_SIZE` | 本地 YOLO provider 推理尺寸 | `1024` | 否 |

当前默认 prompt 策略是 `CC = Inclusive-Icons tile + Inclusive-Icons overview`。记录见 [slice-studio-ai-slice-prompt-strategies.md](slice-studio-ai-slice-prompt-strategies.md)。

OpenRouter / OpenAI-compatible chat-completions example:

```text
SLICE_STUDIO_AI_SLICE_BASE_URL=https://openrouter.ai/api/v1
SLICE_STUDIO_AI_SLICE_API_KEY=
SLICE_STUDIO_AI_SLICE_MODEL=<model-name>
SLICE_STUDIO_AI_SLICE_WIRE_API=chat_completions
```

`chat_completions` keeps the same Slice Studio prompt and output contract. It only changes the provider wire format to `/v1/chat/completions`.

Local YOLO provider example:

```text
SLICE_STUDIO_AI_SLICE_PROVIDER=yolo_local
SLICE_STUDIO_AI_SLICE_YOLO_MODEL_PATH=/Volumes/WorkDrive/Datasets/vins_rico_yolov8/VINS-RICO-UPLABS-ANDROID.v2i.yolov8/runs/detect/runs/detect/train/weights/best.pt
SLICE_STUDIO_AI_SLICE_YOLO_CLASSES=Image,BackgroundImage,Map,Icon,Modal,Drawer
SLICE_STUDIO_AI_SLICE_YOLO_CONFIDENCE=0.35
SLICE_STUDIO_AI_SLICE_YOLO_IMAGE_SIZE=1024
```

`Card` is intentionally excluded from the default YOLO class list because this dataset treats it as a container class that often includes text, buttons, and images together. Use it only for diagnostics or future container-boundary evidence, not as a direct asset slice class.

## Example `.env.local`

```text
NEXT_PUBLIC_SLICE_STUDIO_API_URL=
SLICE_STUDIO_API_URL=http://127.0.0.1:4110
SLICE_STUDIO_LOAD_LOCAL_ENV=true
SLICE_STUDIO_API_PORT=4110
SLICE_STUDIO_AUTH_COOKIE_NAME=slice_studio_session
SLICE_STUDIO_AUTH_SESSION_TTL_DAYS=30
SLICE_STUDIO_AUTH_SECURE_COOKIES=false
SLICE_STUDIO_DOWNLOAD_SIGNING_SECRET=replace-me-before-production
SLICE_STUDIO_DOWNLOAD_URL_TTL_SECONDS=600
SLICE_STUDIO_LOCAL_OWNER_EMAIL=local@slicestudio.dev
SLICE_STUDIO_LOCAL_OWNER_NAME=Local Owner
SLICE_STUDIO_LOCAL_OWNER_PASSWORD=slice-studio-local-owner
SLICE_STUDIO_STORAGE_ROOT=./storage
SLICE_STUDIO_DATABASE_PROVIDER=sqlite
SLICE_STUDIO_DATABASE_URL=
SLICE_STUDIO_ALLOWED_ORIGIN=http://127.0.0.1:3010
SLICE_STUDIO_OCR_PROVIDER=baidu_ppocrv5
SLICE_STUDIO_TEXT_BBOX_SOURCE=m29_ocr_hybrid
SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER=ts_m29_physical_evidence
SLICE_STUDIO_TEXT_STYLE_PROVIDER=psdlike
SLICE_STUDIO_TEXT_STYLE_BASE_URL=http://127.0.0.1:4120
SLICE_STUDIO_TEXT_STYLE_TIMEOUT_SECONDS=8
SLICE_STUDIO_AI_SLICE_PROVIDER=openai_responses
SLICE_STUDIO_AI_SLICE_BASE_URL=https://api.openai.com
SLICE_STUDIO_AI_SLICE_API_KEY=
SLICE_STUDIO_AI_SLICE_MODEL=gpt-5.5
SLICE_STUDIO_AI_SLICE_WIRE_API=responses
SLICE_STUDIO_AI_SLICE_BATCH_CONCURRENCY=4
SLICE_STUDIO_AI_SLICE_YOLO_MODEL_PATH=
SLICE_STUDIO_AI_SLICE_YOLO_CLASSES=Image,BackgroundImage,Map,Icon,Modal,Drawer
BAIDU_PADDLE_OCR_TOKEN=
```

当前默认 storage key 合同：

```text
users/{userId}/projects/{projectId}/originals/{pageId}.png
users/{userId}/projects/{projectId}/exports/assets.zip
users/{userId}/projects/{projectId}/exports/project.zip
users/{userId}/projects/{projectId}/exports/pages/{pageId}/project.zip
```

已有本地旧项目如果仍保存在 `projects/{projectId}/...`，运行时会继续兼容读取；新写入使用 user-scoped 路径。

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
