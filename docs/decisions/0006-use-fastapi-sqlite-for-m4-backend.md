# ADR 0006: M4 后端使用 FastAPI 和 SQLite

- 状态：accepted
- 日期：2026-05-16

## Context

M4 只需要验证后端 API 合同、任务记录和本地资产服务。当前没有复杂查询、并发队列或线上迁移压力。

## Decision

后端使用 FastAPI、Pydantic、uvicorn 和 `uv + backend/pyproject.toml`。数据库使用 SQLite，访问层直接使用 Python 标准库 `sqlite3`。上传成功立即生成 fake DSL 并标记 completed。

## Consequences

好处：

- 本地启动快。
- 依赖少。
- API 合同能先稳定下来。

代价：

- 没有 ORM 抽象。
- 后续真实任务队列和 schema 迁移需要单独补设计。
