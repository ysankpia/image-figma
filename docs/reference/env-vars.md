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
| `TEXT_REPLACEMENT_MODE` | M12 text replacement 模式，支持 `off`、`debug`、`apply` | `debug` | 否 |
| `TEXT_REPLACEMENT_MAX_BLOCKS` | M12 apply 最多接受的 OCR block 数，用作异常 OCR/超长图熔断阀 | `100` | 否 |
| `TEXT_REPLACEMENT_MIN_CONFIDENCE` | M12 replacement 最低 OCR 置信度 | `0.95` | 否 |
| `TEXT_REPLACEMENT_SOLID_BG_TOLERANCE` | M12 低复杂度背景容差 | `18` | 否 |
| `TEXT_REPLACEMENT_MAX_HEIGHT` | M12 可替换 OCR bbox 最大高度 | `64` | 否 |
| `TEXT_REPLACEMENT_MIN_WIDTH` | M12 可替换 OCR bbox 最小宽度 | `12` | 否 |
| `TEXT_REPLACEMENT_MIN_HEIGHT` | M12 可替换 OCR bbox 最小高度 | `10` | 否 |
| `TEXT_REPLACEMENT_ENABLE_COLORED_BG` | 是否允许彩色/深色低复杂度背景上的浅色文字替换 | `true` | 否 |
| `TEXT_REPLACEMENT_MIN_CONTRAST` | replacement 前景文字与背景最小亮度差 | `90` | 否 |
| `TEXT_REPLACEMENT_EDGE_SAMPLE_PADDING` | 背景采样 bbox 外扩像素 | `4` | 否 |
| `TEXT_REPLACEMENT_TEXT_SAMPLE_INSET` | 前景文字采样 bbox 内缩像素 | `1` | 否 |
| `TEXT_REPLACEMENT_UI_AWARE_SAMPLING` | 是否开启 M14 UI-aware 多策略采样，减少 badge、图例、按钮、卡片和底栏文本的 `complex_background` 误杀 | `true` | 否 |
| `TEXT_REPLACEMENT_LOCAL_BG_TOLERANCE` | M14 局部背景采样容差，不改变全局 solid background 容差 | `24` | 否 |
| `TEXT_REPLACEMENT_MAX_RESCUE_STRATEGIES` | 单个 OCR candidate 最多尝试的 M14 rescue 采样策略数 | `4` | 否 |
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

`DSL_PATCH_MODE=apply` 仍不做可见文字替换。M14 可见替换由 `TEXT_REPLACEMENT_MODE=apply` 单独控制，默认 `debug` 只记录 decisions、sampling strategy、quality 和 application。
