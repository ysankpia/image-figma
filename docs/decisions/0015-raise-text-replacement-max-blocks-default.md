# ADR 0015: Raise Text Replacement Max Blocks Default

- 状态：accepted
- 日期：2026-05-17

## Context

M11 使用 `TEXT_REPLACEMENT_MAX_BLOCKS=20` 作为早期安全阀，避免刚接入可见文字替换时一次生成过多 cover/text 节点。M12 已经加入背景/前景采样、低对比拒绝、复杂背景拒绝、状态栏拒绝和 replacement 校验。真实移动端截图 OCR 出 30-80 个文字块很常见，默认 20 会让正常文本因为 `max_blocks_reached` 被拒绝，阻碍覆盖率评估。

## Decision

将 `TEXT_REPLACEMENT_MAX_BLOCKS` 默认值从 `20` 提高到 `100`。

上限机制保留。它不是识别能力限制，而是上线需要的熔断阀，用于防止异常 OCR、超长截图或碎片化结果一次生成过多 Figma 节点。

## Consequences

好处：

- 正常移动端页面不会过早触发 `max_blocks_reached`。
- M12 能真实评估 accepted/rejected 质量，而不是被固定数量截断。
- 仍可通过环境变量在本地或生产环境调低/调高。

代价：

- `TEXT_REPLACEMENT_MODE=apply` 时可能生成更多 cover/text 节点。
- 后续 M13 仍需要做质量控制、区域级开关和更细的回退策略。
