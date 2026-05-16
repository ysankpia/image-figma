# 数据库迁移

v0.1 默认 SQLite。M4 后端已实现本地 SQLite 初始化。

## Current State

- 数据库路径默认：`backend/storage/app.db`。
- schema 在 `backend/app/database.py` 中通过 `CREATE TABLE IF NOT EXISTS` 初始化。
- 当前没有 ORM。
- 当前没有独立迁移脚本。

## Future Rules

后续 schema 变化：

- schema 变化必须更新 [../architecture/data-model.md](../architecture/data-model.md)。
- 迁移必须可重复执行。
- 迁移前后要有验证步骤。
- 不兼容数据变更必须有回滚说明。

## MVP Simplicity

v0.1 不需要复杂迁移系统。可以从初始化 SQL 或 ORM create-all 开始，但必须记录生成方式。
