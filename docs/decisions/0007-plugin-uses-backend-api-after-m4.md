# ADR 0007: 插件在 M5 接入后端 API

- 状态：accepted
- 日期：2026-05-16

## Context

M4 已经提供 FastAPI 假任务流和 `/files/...` 资产服务。继续使用内置 sample DSL 会绕过后端合同，也无法验证图片资产 URL。

## Decision

M5 插件主链路调用 M4 后端 API：上传 PNG、查询任务、获取 DSL，再交给 Renderer。`Sample` 入口保留为开发备用。后端地址暂时固定为 `http://localhost:8000/api`。

## Consequences

好处：

- 插件开始覆盖真实用户路径。
- 后端 DSL 和资产 URL 能被真实 Figma 渲染验证。
- 轮询逻辑提前兼容后续异步任务。

代价：

- 本地验证需要先启动后端。
- API 地址还不能在 UI 中配置。
