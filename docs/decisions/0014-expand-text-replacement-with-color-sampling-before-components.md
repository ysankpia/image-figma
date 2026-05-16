# ADR 0014: Expand Text Replacement With Color Sampling Before Components

- 状态：accepted
- 日期：2026-05-17

## Context

M11 只替换浅色纯色背景上的高置信 OCR 文字。实际样例中大量重要文本位于蓝色按钮、蓝色卡片、badge 和彩色区域上；直接进入组件化或删除 fallback 会把风险放大，因为 OCR bbox 仍不是设计稿布局框。

## Decision

M12 先扩大文字替换覆盖率，而不是做组件化：

- 继续使用 `TextReplacementDocument v0.1`。
- 通过标准库 PNG pixel sampling 估计背景色和文字前景色。
- 接受低复杂度彩色/深色背景上的浅色文字。
- visible text 显式设置字号和行高，避免短 bbox 裁切。
- 对明显同一行的拆分 OCR block 做保守合并。
- fallback region、original reference 和 hidden candidate text 全部保留。

## Consequences

好处：

- 蓝色按钮和卡片上的核心文字可以开始变成可编辑文本。
- replacement 仍可通过 debug decisions 观察和回退。
- 不需要新增图像重依赖或改插件协议。

代价：

- 渐变、复杂纹理、图片区域和组件结构仍保持 fallback。
- 字体族、字重和文本对齐仍只是粗略估计。
- 后续仍需要 M13 做质量控制，M14 以后再做正式可编辑还原和组件绑定。
