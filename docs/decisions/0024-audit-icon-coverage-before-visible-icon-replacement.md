# ADR 0024: Audit Icon Coverage Before Visible Icon Replacement

- 状态：accepted
- 日期：2026-05-17

## Context

M20 已经能在结构索引限定的 component 内裁出高置信 icon PNG candidate，但这还不能说明这些 icon 可以直接放回 Figma 画布。当前 fallback region 仍然保留，直接放回 icon 很容易重复显示；M19 slice 也可能已经覆盖同一区域，后续要决定使用整块 slice 还是 icon + editable text 分层。

还有一个更现实的问题：M20 只裁高置信来源，页面中的 header/back/more/right arrow 等 icon 可能没有被裁出来。直接进入 visible icon fallback 会把漏裁和重复显示混在一起，调试成本很高。

## Decision

M21 新增 icon coverage audit and placement readiness harness：

- 新增 `IconCoverageAuditDocument v0.1`。
- 新增 `/api/tasks/{taskId}/icon-coverage-audit`。
- 新增 `icon_coverage_audit_results` 索引表。
- 默认开启 `ICON_COVERAGE_AUDIT_ENABLED=true`，因为它不改变 Figma 可见输出。
- 对 M20 已裁 icon 生成 placement readiness，标记 ready、needs fallback coordination、needs slice coordination、review required 或 blocked。
- 在低成本区域生成 missedIconHints，但不裁图、不写 icon asset。
- 生成 debug overlay PNG，role 为 `asset_icon_coverage_overlay`。
- 不把 overlay 或 icon 写入 DSL `assets` 数组。
- DSL 只追加顶层 M21 meta。

## Consequences

后续 M22 可以先根据 M21 overlay 和 missed hints 补 icon detection 规则，或在 readiness 足够清楚的区域做 visible icon fallback experiment。M21 让“哪些 icon 已裁、哪些漏了、哪些不能直接放回”变成可测试合同，而不是靠人工翻 storage 目录猜。

M21 不解决 visible icon replacement、partial fallback deletion、SVG 识别、图标库匹配、可编辑矢量重建或复杂形状重建。overlay 只是调试资产，不能影响 Renderer 输入，也不能改变当前 Figma 可见输出。
