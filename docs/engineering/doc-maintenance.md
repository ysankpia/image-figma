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

计划状态必须和目录一致：

- `docs/plans/active/` 只存放真实未完成、下一阶段仍可能执行的计划。
- `docs/plans/completed/` 只存放已经完成并验收过的计划。
- `docs/plans/archive/superseded/` 只存放已被后续计划或 ADR 替代的计划。
- `docs/plans/archive/deferred/` 只存放明确暂缓、未来需要重写或重新排期的计划。

`active` 目录不得存放 `completed`、`deferred` 或 `superseded-by-*` 状态文件。计划移动后，必须同步更新对应目录的 `index.md`，并确保 `docs/index.md` 不再把已完成计划列为 Start Here。

证据收口允许根据代码、测试、架构文档或阶段 commit 证明，把旧 active 计划改为 completed；但执行该动作的阶段计划必须列出证据依据，避免凭印象归档。

计划必须记录：

- 目标。
- 范围。
- 执行步骤。
- 验收。
- 状态。

阶段计划完成后必须和对应代码、测试、ADR 一起进入独立阶段 commit。下一阶段不能复用上一阶段的 dirty tree；如果上一阶段还有验收后修正，先用同阶段 fix commit 收口，再创建下一阶段计划。
