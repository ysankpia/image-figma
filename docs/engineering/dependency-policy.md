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

- Monorepo：pnpm workspace，当前已初始化。
- 插件：TypeScript + 静态 `ui.html`；React/Vite 只在后续 UI 复杂度真实需要时再评估。
- 共享包：TypeScript，当前已实现 `@image-figma/dsl-schema` 和 `@image-figma/image-to-figma-renderer`。
- 后端：Python、FastAPI、Pydantic。
- 数据库：SQLite，M4 使用 Python 标准库 `sqlite3`，暂不引入 ORM。
- 测试：按实际代码栈选择 Vitest、pytest、Playwright。

## Current Dependencies

当前引入：

- `typescript`：共享包类型检查。
- `vitest`：`dsl-schema` 单元测试。
- `@types/node`：测试和 Node 工具类型。
- `ajv`：测试 JSON Schema 与示例 DSL 的兼容性。
- `@figma/plugin-typings`：Figma 插件 Main 类型。
- `tsup`：构建 Figma 插件 Main 和 dev harness，当前 Figma bundle target 固定为 `es2017`。
- `fastapi`：M4 后端 API。
- `uvicorn`：本地运行 FastAPI。
- `pydantic`：后端数据结构和 FastAPI 依赖。
- `python-multipart`：处理 PNG multipart 上传。
- `pytest`、`httpx`：后端 API 测试。

这些依赖只服务 DSL 合同、Renderer、Figma 插件最小闭环和 M4 后端假任务流，没有引入 React/Vite、ORM、队列或 CI。

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
