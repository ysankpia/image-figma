# ADR 0004: Renderer 通过 FigmaAdapter 调用 Figma API

- 状态：accepted
- 日期：2026-05-16

## Context

Renderer 需要在 Figma 插件环境创建节点，但大部分渲染逻辑应该能在 Node 测试中验证。如果每个模块直接使用全局 `figma`，测试会困难，错误也会扩散到所有渲染文件。

## Decision

Renderer 只依赖 `FigmaAdapter`。真实 Figma 插件环境通过 `createFigmaAdapter(figma)` 包装全局 API。单元测试使用 fake adapter。

## Consequences

好处：

- Renderer 纯逻辑可以用 Vitest 覆盖。
- Figma API 变化集中在一个边界层。
- dev harness 能验证真实画布写入，而不污染核心渲染模块。

代价：

- Adapter 需要持续补齐 Figma 能力。
- 某些真实 Figma 行为仍需要插件环境烟测，不能只靠 Node 单测。
