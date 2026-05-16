# ADR 0010: AI 只提出 Visual Primitives，不直接生成 DSL

- 状态：accepted
- 日期：2026-05-16

## Context

《Thinking with Visual Primitives》这类范式说明，多模态模型的价值不只是给 UI 截图贴语义标签，还可以输出可引用的视觉坐标，例如区域、卡片、按钮底板、图标、图片和分割线。问题是，模型输出天然不该被当成权威结构。它可能漏检、重复、越界、坐标系混乱，甚至把语义解释和布局生成混在一起。

本项目的硬边界是 DSL v0.1。Renderer 只信 DSL，DSL 必须可校验。让 AI 直接输出 DSL，会把模型不确定性直接塞进跨端合同，这是错误的系统边界。

## Decision

M8 引入独立 `VisualPrimitiveDocument v0.1`，让 AI/OCR/CV 的结果先落成候选 visual primitives：

- bbox 使用整图像素坐标 `[x, y, width, height]`。
- primitives 是候选输入，不是 DSL。
- 默认 provider 为 `fake`，用于合同、测试和调试。
- 可选 `openai` provider 只在 `VISUAL_PRIMITIVE_PROVIDER=openai` 时启用。
- OpenAI provider 使用 Responses API structured JSON output。
- OpenAI provider 分 region 调用，不把整张长图一次性丢给模型。
- 模型输出必须经过 validator，非法 bbox、重复 id、无效 relation 被丢弃或降级。
- primitive extraction 失败不影响 M7 deterministic DSL 和插件渲染。

M9 才允许把 OCR boxes + visual primitives 合并成 DSL patch，并且 patch 必须经过 DSL validator。

## Consequences

好处：

- DSL 仍是唯一权威合同。
- 模型失败不会拖垮上传主链路。
- 可以单独调试 AI 的空间引用质量。
- M9 合并逻辑有明确输入边界，不需要反向解析模型生成的 DSL。

代价：

- M8 还不会提升 Figma 输出质量。
- 多了一份 primitive JSON 和 `primitive_results` 表。
- OpenAI provider 只是可选 smoke 能力，真实效果要到 M9/M10 才能体现。

## Non-Goals

- 不做 OCR。
- 不生成可编辑文字。
- 不做 Auto Layout。
- 不做组件化。
- 不让模型直接输出 DSL。
