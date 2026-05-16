# M4 FastAPI 后端假任务流计划

- 状态：completed
- 创建日期：2026-05-16
- 负责人：Codex

## Goal

实现最小 FastAPI 后端，用 SQLite 和本地文件存储跑通 PNG 上传、completed 假任务、DSL 查询和资产 URL。

## Scope

包含：

- `GET /api/health`。
- `POST /api/upload`。
- `GET /api/tasks/{taskId}`。
- `GET /api/tasks/{taskId}/dsl`。
- `GET /api/assets/{assetId}`。
- `/files/uploads` 和 `/files/assets` 静态文件。
- pytest API 测试。

不包含：

- 插件接 API。
- OCR/AI。
- 真实裁切。
- 队列。
- 用户、支付、额度。
- ORM 或迁移系统。

## Steps

1. 建立 `backend/pyproject.toml` 和 uv 依赖。状态：完成。
2. 实现 FastAPI app、SQLite 初始化和本地存储。状态：完成。
3. 实现 health/upload/task/dsl/assets API。状态：完成。
4. 基于 mobile-home 示例生成 fake DSL。状态：完成。
5. 补 pytest 覆盖主路径和错误路径。状态：完成。
6. 同步架构、API、数据模型和运行文档。状态：完成。

## Acceptance

- 合法 PNG 上传后返回 completed task。
- 非 PNG 和过大 PNG 返回稳定错误码。
- task 查询返回状态。
- completed task 能返回 DSL。
- asset 元信息可查询。
- `/files/...` 能返回 PNG。

## Validation

```bash
cd backend
uv run pytest
pnpm run check
```

## Notes

M4 不改 Figma 插件。插件接后端放到 M5。
