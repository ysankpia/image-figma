# ADR: Test M29 Direct Replay Before More Unit Promotion

- 状态：proposed
- 日期：2026-05-22

## Context

当前主线已经完成 M30 可见图层物化、M37 readiness、M38 安全层级物化和 M39/M39.1 结构诊断。但项目出现了一个架构层面的疑问：是否过早把重点放到 unit/container/grouping，而 M29 本身已经能拆出足够强的 visual primitive，可以先直接回放成一个扁平但可用的 Figma draft。

第一性原理下，真实目标不是“生成更多 readiness report”，而是让单张 PNG 变成高保真、可编辑、可拖动的 Figma 页面。M29 保存的是接近源像素的 evidence，OCR 保存的是可编辑文字证据。二者可能组成一条更短的 draft path。

## Decision

在 `experiment/m29-direct-replay` 分支上实现 M29 Direct Replay 实验：

```text
source PNG + OCR text boxes + M29 nodes
-> flat DSL v0.1
-> existing renderer
```

实验只新增脚本和报告，不接入默认上传 pipeline，不替换 M30/M37/M38/M39。OCR text 优先于重叠的 M29 raster evidence；M29 image/symbol/simple shape 可回放成 DSL node；blocked/unknown 只进入 report。

## Consequences

好处：

- 用最小实验验证当前路线是否过度依赖中间层。
- 如果 M29 direct replay 足够好，可以把当前主线降级为质量门和结构增强，而不是唯一 draft path。
- 如果效果不好，主线不受污染，可以继续 M39.1.1/M39.2。

代价：

- 会产生一条实验性旁路，需要明确文档和分支边界。
- 裸 M29 没有 OCR 时不能产出 editable text，只能验证 pixel splitting。
- flat replay 不解决组件化、Auto Layout 和语义层级，只验证“可用 draft”能力。
