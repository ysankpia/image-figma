# 0027. Experiment With Visible Icon Fallback After Placement Plan

- 状态：Accepted
- 日期：2026-05-17

## Context

M20/M22 已经能裁出一部分 icon PNG，M23 已经把这些 icon 统一成 placement plan，并明确哪些位于 fallback region 内。直接把这些 icon 放进画布会和 fallback 原图里的同一图标形成双影；如果同时删除整块 fallback，又会破坏当前整页视觉稳定性。

因此第一个可见 icon 阶段不能做全量替换，也不能处理所有漏裁。它应该只验证一个最小事实：已裁出的低风险 icon，能否通过局部 cover + image node 的方式变成 Figma 中独立可选、可拖动的图层。

## Decision

M24 做 visible icon fallback replay experiment：

- 默认关闭：`ICON_VISIBLE_FALLBACK_ENABLED=false`。
- 只消费 M23 `placements[]`，不重新裁图，不消费 M21 hints，不处理 M22 blocked hints。
- 只回放 `decision == needs_fallback_mask` 且 role 在 allowlist 内的低风险 placement。
- 用 `icon_fallback_cover` shape 遮住 fallback 原图里的 icon。
- 用 `visible_icon_fallback` image node 放回已裁 icon PNG。
- 只把实际 applied 的 icon asset 追加进 DSL `assets`。
- 生成 `/icon-visible-fallback` 报告和 debug overlay。

## Consequences

好处：

- 第一次让 icon PNG 变成独立可选图层，但实验范围受控。
- fallback 不被删除，整页稳定性仍有兜底。
- 通过 solid background sampling 阻断复杂背景，避免明显双影和脏 cover。
- 后续 M25/M26 可以独立处理漏裁补强，不污染可见回放实验。

代价：

- M24 只覆盖 nav/header/leading icon，不覆盖 field/trailing/button。
- icon PNG 仍是 crop，不是透明 SVG，可能带少量背景像素。
- 背景不稳定时会 blocked，宁可漏放，不强行回放。
- M24 不是 Codia 式全量可拖动层。

## Non-Goals

- 不处理没拆出来的 icon。
- 不补 M21 missed hints。
- 不处理 M22 blocked hints。
- 不做新的 icon crop。
- 不做全局 icon detection。
- 不做 Codia 式全量拆层。
- 不做透明 PNG、SVG 或 icon semantic recognition。
- 不做图标库替换。
- 不删除 fallback。
- 不引入 Pillow/OpenCV。
