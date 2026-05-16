# ADR 0016: Use Quality Gate Before Formal Text Replacement

- 状态：accepted
- 日期：2026-05-17

## Context

M12 已能把一部分低复杂度背景 OCR 文本变成可见 Figma Text，但真实页面里还有大量边界情况：badge、提示卡、图例、插画附近文本和卡片阴影。直接放宽 `complex_background` 会提高覆盖率，但也会增加遮盖图标、遮盖插画、双层文字和错误 cover 的风险。

## Decision

M13 先增加 text replacement quality gate：

- 保留 M12 基础 decision。
- 每个 decision 增加 quality score、risk、region 和 reason summary。
- apply 时只写入低风险 accepted replacement。
- 中高风险 accepted replacement 被记录但不进入 DSL。
- rejected replacement 继续 rejected，不在 M13 放宽。

## Consequences

好处：

- 可以区分 OCR 缺失、replacement 拒绝和质量门禁阻断。
- apply 比 M12 更保守，坏遮盖风险更低。
- M14 可以基于稳定报告定向放开 badge、button、tip、legend 等场景。

代价：

- M13 不会显著提高可编辑文字覆盖率。
- 一些 M12 可替换文本可能因质量门禁被阻断，需要后续按区域优化。
