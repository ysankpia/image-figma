# ADR 0001: 使用 DSL v0.1 作为跨端合同

- 状态：accepted
- 日期：2026-05-16

## Context

项目包含后端识别管线、Figma 插件和 Renderer。若后端直接驱动 Figma 节点，或者插件直接理解 OCR/AI 输出，边界会很快失控。

## Decision

使用 DSL v0.1 作为唯一跨端合同。

后端负责生成并校验 DSL。Renderer 只消费 DSL 并写入 Figma。插件 UI 不理解 DSL 内部细节，只展示用户流程状态。

## Consequences

好处：

- 后端和 Renderer 可以并行开发。
- 假 DSL 能先验证 Figma 渲染可行性。
- API、Renderer、测试可以围绕同一合同收敛。

代价：

- DSL 字段变更必须谨慎。
- 所有跨端行为变化都要更新 DSL 文档和测试。
