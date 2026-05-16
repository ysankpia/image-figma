# 数据库迁移

v0.1 默认 SQLite。当前仓库尚未实现数据库。

## Current State

无数据库文件、无迁移脚本、无 ORM。

## Future Rules

后续引入数据库后：

- schema 变化必须更新 [../architecture/data-model.md](../architecture/data-model.md)。
- 迁移必须可重复执行。
- 迁移前后要有验证步骤。
- 不兼容数据变更必须有回滚说明。

## MVP Simplicity

v0.1 不需要复杂迁移系统。可以从初始化 SQL 或 ORM create-all 开始，但必须记录生成方式。
