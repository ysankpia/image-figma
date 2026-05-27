# Bug Ledger

本目录记录 shipped bug、根因、修复和回归保护。

当前 open bug：

- [009-specialization-prone-m29-internal-asset-gates.md](open/009-specialization-prone-m29-internal-asset-gates.md)：M29 internal asset chain 已避免硬特化，但仍有 OCR-anchor evidence bias、confidence gate drift 和 anti-specialization guard 缺口。
- [003-text-replacement-rejects-ui-labels-on-low-complexity-cards.md](open/003-text-replacement-rejects-ui-labels-on-low-complexity-cards.md)：M12 replacement 对部分已 OCR 识别 of UI 文本仍判为 `complex_background`。

最近 resolved bug：

- [018-controlled-structure-and-control-icon-model-first-regression.md](resolved/018-controlled-structure-and-control-icon-model-first-regression.md)：model-first interactive 不再把 C-stage 结构组写成可见 DSL group，并为纵向 action tile 推导 icon source。
- [017-residual-media-overlays-foreground-claims.md](resolved/017-residual-media-overlays-foreground-claims.md)：model-first foreground claim 已进入 M29.5，但 parent residual media image 在 DSL 层级上盖住 foreground shape/text，导致按钮被擦成白底或空心。
- [016-media-contained-long-control-label-preserved-as-raster.md](resolved/016-media-contained-long-control-label-preserved-as-raster.md)：media 内长 UI 控件 label 不再仅因 OCR bbox 较高/较宽被归为 `preserve_raster_text`，Google/Snapchat 这类已 OCR 的登录方式文本现在能进入 `editable_ui_text / text_replay`，真正大 display text 仍保留在 raster。
- [015-bottom-tab-selected-icon-stays-non-ocr-foreground.md](resolved/015-bottom-tab-selected-icon-stays-non-ocr-foreground.md)：selected bottom tab icon 现在通过 near-media OCR anchor、evidence-aware soft-edge alpha、evidence contract、promotion、M29.5 去重和 ownership conservation 成为独立 `icon_replay`，selected indicator 仍保持 diagnostic。
- [014-fragmented-internal-icon-fails-transparent-asset-gate.md](resolved/014-fragmented-internal-icon-fails-transparent-asset-gate.md)：图内 action row icon 被切成相邻碎片时，现在由 M29.6 生成同 OCR anchor 的 union candidate，再通过 transparent/evidence/promotion/M29.5 主链成为可选 icon。
- [011-finite-control-backgrounds-can-be-preserved-as-media.md](resolved/011-finite-control-backgrounds-can-be-preserved-as-media.md)：有限按钮/控件背景现在在 source evidence 支持时进入 `control_background / shape_geometry / shape_replay`，并由 M29.5 裁剪无效 copied cleanup target。
- [012-bottom-tab-icons-stay-diagnostic-inside-composite-media.md](resolved/012-bottom-tab-icons-stay-diagnostic-inside-composite-media.md)：底部 tab 图标在 low-confidence composite media 内被 raw M29 blocked evidence 捕获后，现在通过 M29.2 label-anchor recovery 恢复为 `raster_icon / icon_replay`，并由 M29.5 授权 copied media cleanup。
- [013-dsl-visual-comparison-text-noise-dominates-gate.md](resolved/013-dsl-visual-comparison-text-noise-dominates-gate.md)：DSL visual comparison 的近似文字渲染误差主导全图 diff，导致 061 真实样本质量 gate 容易被诊断字体噪声带偏。
- [010-dsl-visual-comparison-text-renders-as-solid-bars.md](resolved/010-dsl-visual-comparison-text-renders-as-solid-bars.md)：DSL visual comparison 的 report-only 近似渲染把 text 节点画成实心条，容易误导 525 artifact inspection。
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
