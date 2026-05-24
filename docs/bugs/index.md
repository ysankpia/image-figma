# Bug Ledger

本目录记录 shipped bug、根因、修复和回归保护。

当前 open bug：

- [003-text-replacement-rejects-ui-labels-on-low-complexity-cards.md](open/003-text-replacement-rejects-ui-labels-on-low-complexity-cards.md)：M12 replacement 对部分已 OCR 识别 of UI 文本仍判为 `complex_background`。

最近 resolved bug：

- [008-fallback-off-dark-ui-white-collapse.md](resolved/008-fallback-off-dark-ui-white-collapse.md)：M29 fallback-off 深色 UI 暴露固定浅色背景，根因是 raster/media preservation 没有回归 M29.2/M29.5 主链。
- [007-composite-media-outer-shell-duplicates-top-tab-text.md](resolved/007-composite-media-outer-shell-duplicates-top-tab-text.md)：M30.7 同时物化紧轮播图和外层 chrome shell，导致顶部 tab 文本被底层 raster 与上层 text 重复绘制。
- [006-missing-text-nodes-not-added-to-fallback-single-nodes.md](resolved/006-missing-text-nodes-not-added-to-fallback-single-nodes.md)：M29.0.4 未配对/未聚类成功的孤立文本节点未被 fallback 兜底添加，导致 DSL 丢失文本。
- [005-m2902-preview-hides-accepted-image-evidence.md](resolved/005-m2902-preview-hides-accepted-image-evidence.md)：M29.0.2 只在 JSON/overlay 记录 accepted image 和 M29.1 group，没有导出 preview crop，导致轮播图等证据在底部证据区不可见。
- [004-icon-gap-multiple-blocked-hints-fail-validation.md](resolved/004-icon-gap-multiple-blocked-hints-fail-validation.md)：M22 多个 blocked hints 共用候选计数生成重复 id，导致真实图 `icon-gap-candidates` 文档校验失败。

## Structure

- `open/`：未解决 bug。
- `resolved/`：已解决 bug。
- `template.md`：bug 记录模板。

## Rules

修复 bug 前必须：

- 记录复现方式。
- 记录影响范围。
- 定位根因。
- 加回归保护。
- 写验证证据。

没有回归保护，不关闭 bug。无法自动化时必须解释原因。
