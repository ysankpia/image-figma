# 环境变量

当前仓库没有运行时代码，因此没有必需环境变量。

## Future Variables

后续可能需要：

| 名称 | 用途 | 默认值 | 是否必需 |
| --- | --- | --- | --- |
| `API_BASE_URL` | 插件调用后端 API | `http://localhost:8000/api` | 是 |
| `OPENAI_API_KEY` | AI 视觉模型调用 | 无 | 接入 AI 后是 |
| `STORAGE_ROOT` | 本地文件存储根目录 | `backend/storage` | 后端实现后是 |
| `DATABASE_URL` | SQLite 数据库路径 | `sqlite:///backend/storage/app.db` | 后端实现后是 |

真实密钥不得写入仓库。
