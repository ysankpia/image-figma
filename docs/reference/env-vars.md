# 环境变量

当前后端和插件已有本地运行代码。后端都有默认值，不需要 `.env` 才能启动。

## Variables

| 名称 | 用途 | 默认值 | 是否必需 |
| --- | --- | --- | --- |
| `API_BASE_URL` | 插件调用后端 API | `http://localhost:8000/api` | 当前插件硬编码同值，后续设置页再读取 |
| `PUBLIC_BASE_URL` | 后端生成 `/files/...` URL | `http://localhost:8000` | 否 |
| `CORS_ALLOW_ORIGINS` | 允许浏览器/Figma 插件调用后端的 Origin，逗号分隔 | `*` | 否 |
| `VISUAL_PRIMITIVE_PROVIDER` | M8 primitive provider，支持 `fake`、`openai` | `fake` | 否 |
| `OCR_PROVIDER` | OCR provider，支持 `fake`、`baidu_ppocrv5` | `fake` | 否 |
| `OCR_MIN_CONFIDENCE` | OCR block 最低置信度，低于该值丢弃 | `0.70` | 否 |
| `DSL_PATCH_MODE` | M9 DSL patch 模式，支持 `off`、`debug`、`apply` | `debug` | 否 |
| `BAIDU_PADDLE_OCR_TOKEN` | 百度 AI Studio OCR bearer token | 无 | 仅 `OCR_PROVIDER=baidu_ppocrv5` 时需要 |
| `BAIDU_PADDLE_OCR_JOB_URL` | 百度 AI Studio OCR jobs endpoint | `https://paddleocr.aistudio-app.com/api/v2/ocr/jobs` | 否 |
| `BAIDU_PADDLE_OCR_MODEL` | 百度 OCR 模型 | `PP-OCRv5` | 否 |
| `BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS` | 百度异步 OCR 轮询间隔 | `5` | 否 |
| `BAIDU_PADDLE_OCR_TIMEOUT_SECONDS` | 百度异步 OCR 单任务超时 | `120` | 否 |
| `OPENAI_API_KEY` | OpenAI primitive provider 密钥 | 无 | 仅 `VISUAL_PRIMITIVE_PROVIDER=openai` 时需要 |
| `OPENAI_VISION_MODEL` | OpenAI primitive provider 使用的视觉模型 | `gpt-5.5` | 否 |
| `OPENAI_TIMEOUT_SECONDS` | OpenAI 请求超时秒数 | `30` | 否 |
| `STORAGE_ROOT` | 本地文件存储根目录 | `backend/storage` | 否 |
| `DATABASE_PATH` | SQLite 数据库路径 | `backend/storage/app.db` | 否 |
| `MAX_UPLOAD_BYTES` | PNG 上传大小上限 | `10485760` | 否 |

真实密钥不得写入仓库。

默认 `fake` provider 不调用 OpenAI 或百度，也不需要外部密钥。

`BAIDU_PADDLE_OCR_TOKEN` 是 bearer token，必须只通过本地环境变量或未提交的 `.env` 提供，不能写入仓库。

M10 中 `DSL_PATCH_MODE=apply` 只保留配置入口，行为仍不做可见文字替换；真正可见替换放到 M11。
