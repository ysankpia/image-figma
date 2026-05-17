# 0026. Plan Icon Placement Before Visible Icon Layers

- 状态：Accepted
- 日期：2026-05-17

## Context

M20 已经能裁出 text/component-guided icon PNG。M21 已经能审计覆盖、漏裁 hints 和 placement readiness。M22 已经能把部分高价值漏裁区域补裁成 gap icon PNG。

用户的长期目标接近 Codia 式可拖动图层，但当前 fallback region 仍然保留。如果直接把 M20/M22 icon PNG 放回画布，会和 fallback 原图里的同一个 icon 重复显示，也可能和 M19 component slice、visible text、cover 或 hidden candidate_text 冲突。

## Decision

M23 先做 icon placement plan/layering readiness harness：

- 合并 M20 icon candidates 和 M22 gap icon candidates。
- 对重复 icon 做 dedupe，不静默丢弃。
- 基于当前 DSL、M19 slice candidates 和引用完整性计算 collision。
- 输出 `ready_for_visible_icon`、`needs_fallback_mask`、`needs_slice_coordination`、`needs_fallback_coordination`、`review_required`、`blocked` 和 `deduped`。
- 生成 `futureDslNodeHint`，但只写入 report。
- 生成 `icon_placement_overlay.png`，但只作为调试资产。
- 只追加 DSL 顶层 meta，不改变 Figma 可见输出。

## Consequences

好处：

- M24 可以基于明确计划做小范围 visible icon fallback experiment，而不是硬塞 image node。
- fallback 重复显示、slice 冲突和 text/cover 冲突在可见替换前被显式暴露。
- M20/M22 的 icon asset pool 有统一入口和去重规则。

代价：

- M23 不让 icon 立即可拖动。
- 大多数位于 fallback region 内的 icon 会被标为 `needs_fallback_mask`，需要 M24+ 处理 mask 或 partial fallback replacement。
- M23 不解决 SVG/icon 语义识别，也不做全局 icon detection。

## Non-Goals

- 不裁新 icon。
- 不新增可见 DSL 节点。
- 不修改 DSL `assets`。
- 不删除 fallback。
- 不把 icon 放进 Figma 画布。
- 不做 Codia 式全量可拖动图层。
- 不做全局 icon detection。
- 不做 SVG/icon semantic recognition。
- 不做图标库匹配。
- 不接 AI 或 inpainting。
- 不引入 Pillow/OpenCV。
