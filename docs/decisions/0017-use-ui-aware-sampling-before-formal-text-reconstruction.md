# ADR 0017: Use UI-aware Sampling Before Formal Text Reconstruction

- 状态：accepted
- 日期：2026-05-17

## Context

M13 已经能解释 replacement 的 accepted/rejected/blocked 状态，但真实首页样例里仍有一类明显问题：百度 PP-OCRv5 已识别出文本，replacement 却在基础采样阶段被判为 `complex_background`。这些文本通常位于 badge、图例、outline button、提示卡、预览卡或底部导航中。标准 perimeter sampling 会采到色块、边框、阴影、图标或插画边缘，导致背景复杂度被高估。

直接调大 `TEXT_REPLACEMENT_SOLID_BG_TOLERANCE` 会把真正复杂背景也放进来，增加遮盖图标、双层文字和错误 cover 的风险。

## Decision

M14 在正式文本重建前增加 UI-aware sampling：

- 保留标准 perimeter sampling 作为第一策略。
- 仅在标准策略出现可救失败时尝试局部 rescue。
- 为 badge、legend、outline button、card/tip 和 bottom nav 文本使用更窄的局部背景采样。
- 每个 decision 记录 `strategy.attempts`，让 `/text-replacements` 能解释为什么被救回或继续拒绝。
- 不改 OCR provider、插件协议、Renderer、DSL 节点结构或 SQLite 表。

## Consequences

好处：

- 可以提高已 OCR 文本变成可编辑 Text 的覆盖率。
- 仍能保留 M13 quality gate 和 fallback 安全边界。
- 对 `complex_background` 误杀有可观测的 strategy 证据。

代价：

- UI-aware sampling 是启发式，不等于正式组件理解。
- 对插画、纹理、渐变或图标重叠区域仍可能保持 rejected。
- 后续 M15 仍需要把 OCR text 和 visual primitives 绑定，M16 才进入组件化和布局重建。
