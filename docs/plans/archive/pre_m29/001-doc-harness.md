# 文档 Harness 整理

- 状态：active
- 创建日期：2026-05-16
- 负责人：Codex

## Goal

把现有 16 份散落草稿整理成 agent-first 文档 harness，让后续实现可以从仓库文件读取产品、架构、工程规则、计划、bug 和决策。

## Scope

包含：

- 归档旧草稿到 `docs/reference/legacy/`。
- 创建 `AGENTS.md`、`README.md`、`docs/index.md`。
- 补齐 product、architecture、engineering、runbooks、reference、decisions、plans、bugs 文档。
- 保持正式文档精简，提炼旧草稿结论。

不包含：

- 不创建代码骨架。
- 不创建 scripts。
- 不创建 CI。
- 不实现 DSL、Renderer、后端或插件。
- 不运行 project-harness 完整脚手架。

## Steps

1. 创建文档目录。
2. 移动旧草稿到 legacy。
3. 编写入口文档。
4. 编写 product 文档。
5. 编写 architecture 文档。
6. 编写 engineering、runbooks、reference 文档。
7. 编写 ADR、计划和 bug ledger。
8. 验证结构、链接、占位符和范围。

## Acceptance

- `docs/index.md` 可以导航到所有正式文档。
- 原 16 份草稿全部在 legacy 中登记。
- 正式文档没有模板占位符残留。
- 没有新增代码目录、脚本、CI 或依赖配置。
- 文档之间没有明显 API、DSL、MVP 范围冲突。

## Validation

- 检查文档结构。
- 检查 legacy 文件数量。
- 检查 Markdown 相对链接。
- 检查常见模板占位文本。
- 检查范围外目录不存在。
