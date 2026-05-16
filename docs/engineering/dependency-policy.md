# 依赖策略

依赖不是免费午餐。每个依赖都会增加安装、升级、调试和 agent 理解成本。

## Rules

- 优先使用语言和框架标准能力。
- 不为少量代码引入大型依赖。
- 不引入无人维护或冷门依赖。
- 不在没有计划的情况下引入新包管理器。
- 新依赖必须说明用途、替代方案和验证方式。

## Preferred Defaults

后续实现的默认技术选择：

- Monorepo：pnpm workspace。
- 插件：TypeScript、React、Vite。
- 共享包：TypeScript。
- 后端：Python、FastAPI、Pydantic。
- 数据库：SQLite。
- 测试：按实际代码栈选择 Vitest、pytest、Playwright。

## AI/OCR Dependencies

OCR 和 AI 依赖应包装在清晰 client 层。业务代码不直接散落调用外部 SDK。

模型调用必须有：

- 超时。
- 错误码。
- 调用摘要日志。
- 可替换边界。

## Review Requirement

任何新增依赖都必须更新：

- 本文件。
- 本地设置 runbook。
- 对应测试或验证说明。
