# ADR 0023: Crop Icon Candidates Before Visible Partial Replacement

- 状态：accepted
- 日期：2026-05-17

## Context

M19 已经能为低风险 component 生成本地 slice PNG，但它处理的是 component 级区域。真实移动端页面还有大量小 icon，例如底部导航图标、快捷入口图标、提示标题图标和详情字段前导图标。

`png_tools.crop_png()` 已经能裁 PNG。真正缺的是 icon bbox discovery。如果 M21/M22 直接开始可见替换，却没有 icon 候选资产，系统只能继续把 icon 留在大块 fallback 或 component slice 里，文字和图标很难分层。

## Decision

M20 新增 icon candidate extraction and crop harness：

- 新增 `IconCandidateDocument v0.1`。
- 新增 `/api/tasks/{taskId}/icon-candidates`。
- 新增 `icon_candidate_results` 索引表。
- 默认开启 `ICON_CANDIDATE_ENABLED=true`，因为它不改变 Figma 可见输出。
- 只在 M15-M17 已有结构索引限定的 component search window 内找小型前景块。
- 使用 `decode_png_pixels()` 做局部背景估算和 connected component，使用 `crop_png()` 生成 PNG。
- 生成的 icon PNG 写入本地 storage 和 `assets` 表，role 为 `asset_icon_candidate`。
- 不把 icon asset 写入 DSL `assets` 数组。
- DSL 只追加顶层 M20 meta。

## Consequences

后续 M21/M22 可以基于 M20 的 icon PNG 候选做 visible icon fallback 或 partial fallback replacement，而不是盲目从整图裁 icon。

M20 不解决 SVG 识别、图标库匹配、Lucide/Material 替换、可编辑矢量重建、复杂形状重建或正式局部 fallback 删除。失败或低置信 icon 只进入报告，不影响 upload completed 和当前 Figma 可见输出。
