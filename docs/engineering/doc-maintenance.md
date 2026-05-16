# 文档维护

文档漂移就是仓库 bug。

## Update Rules

以下变化必须更新文档：

- 产品行为。
- 用户流程。
- DSL 字段。
- API 合同。
- 数据模型。
- 环境变量。
- 运行命令。
- 架构边界。
- 验收标准。
- 重大技术决策。

## Source Of Truth

正式规格在：

- `docs/product/`
- `docs/architecture/`
- `docs/engineering/`
- `docs/runbooks/`
- `docs/reference/`
- `docs/decisions/`

历史草稿在 `docs/reference/legacy/`，只作背景，不作当前规范。

## Link Hygiene

新增文档必须：

- 使用相对链接。
- 从 `docs/index.md` 可达。
- 避免复制旧草稿的大段内容。
- 明确当前结论和非目标。

## Plan Hygiene

完成的计划移动到 `docs/plans/completed/`。活跃计划留在 `docs/plans/active/`。

计划必须记录：

- 目标。
- 范围。
- 执行步骤。
- 验收。
- 状态。
