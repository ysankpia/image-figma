# 环境变量

当前后端和插件已有本地运行代码。后端都有默认值，不需要 `.env` 才能启动。

## Variables

| 名称 | 用途 | 默认值 | 是否必需 |
| --- | --- | --- | --- |
| `API_BASE_URL` | 插件调用后端 API | `http://localhost:8000/api` | 当前插件硬编码同值，后续设置页再读取 |
| `PUBLIC_BASE_URL` | 后端生成 `/files/...` URL | `http://localhost:8000` | 否 |
| `CORS_ALLOW_ORIGINS` | 允许浏览器/Figma 插件调用后端的 Origin，逗号分隔 | `*` | 否 |
| `VISUAL_PRIMITIVE_PROVIDER` | M8 primitive provider，支持 `fake`、`openai` | `fake` | 否 |
| `OPENAI_API_KEY` | OpenAI primitive provider 密钥 | 无 | 仅 `VISUAL_PRIMITIVE_PROVIDER=openai` 时需要 |
| `OPENAI_VISION_MODEL` | OpenAI primitive provider 使用的视觉模型 | `gpt-5.5` | 否 |
| `OPENAI_TIMEOUT_SECONDS` | OpenAI 请求超时秒数 | `30` | 否 |
| `STORAGE_ROOT` | 本地文件存储根目录 | `backend/storage` | 否 |
| `DATABASE_PATH` | SQLite 数据库路径 | `backend/storage/app.db` | 否 |
| `MAX_UPLOAD_BYTES` | PNG 上传大小上限 | `10485760` | 否 |

真实密钥不得写入仓库。

默认 `fake` provider 不调用 OpenAI，也不需要 `OPENAI_API_KEY`。
