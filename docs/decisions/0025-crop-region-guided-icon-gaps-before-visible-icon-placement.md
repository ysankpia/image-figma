# 0025. Crop Region-Guided Icon Gaps Before Visible Icon Placement

- 状态：Accepted
- 日期：2026-05-17

## Context

M20 已经能基于文字和组件关系裁出一批低风险 icon PNG。M21 已经能审计这些 icon 的覆盖情况，并把 header、trailing、bottom nav、shortcut、field 等区域的漏裁疑点写成 `missedIconHints` 和 overlay。

用户的最终目标接近 Codia 式图层拆分：页面里的多个 icon 后续应该能成为可单独拖动的图层。但直接在当前阶段做全局 icon detection 或可见 icon replacement 风险太高，容易把文字笔画、状态栏、插画碎片、按钮边框和系统胶囊误裁成 icon。

## Decision

M22 先做 region-guided icon gap candidate harness：

- 消费 M21 `missedIconHints`。
- 只对 header、bottom nav、shortcut、card/row/button trailing 等高价值局部区域补裁。
- 使用现有标准库 PNG 工具裁出本地 `icons_gap/*.png` 候选资产。
- 生成 `icon_gap_candidates/{taskId}.json` 和 `icon_gap_overlay.png`。
- 只追加 DSL 顶层 meta，不改变 Figma 可见输出。

顶部右侧小程序胶囊只裁内部 dots/circle 这类小 blob，不裁整块胶囊。字段页默认保守，疑似文字笔画或 hidden candidate_text 区域只写 blocked。

## Consequences

好处：

- M20 漏掉的 header/trailing/bottom nav/shortcut icon 可以进入候选资产池。
- M21 overlay 暴露的问题有明确的下一步消费路径。
- M23/M24 可以基于 M20 + M22 资产做 placement plan 或小范围 visible icon fallback experiment。

代价：

- M22 仍然不是完整全局 icon detector。
- 没有文字或结构关系、也不在高价值区域里的孤立 icon 仍可能漏掉。
- M22 不解决 SVG/icon 语义识别，也不让 icon 立即可拖动。

## Non-Goals

- 不做全图无边界 icon 扫描。
- 不做 Codia 式全量可拖动图层。
- 不新增可见 DSL 节点。
- 不修改 DSL `assets`。
- 不删除 fallback。
- 不做 SVG/icon semantic recognition。
- 不做图标库匹配。
- 不按中文文案特化。
- 不接 AI 或 inpainting。
- 不引入 Pillow/OpenCV。
