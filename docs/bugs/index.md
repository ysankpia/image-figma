# Bug Ledger

本目录记录 shipped bug、根因、修复和回归保护。

当前分支的主线是 Editable Draft Layer Pipeline。Codia Beta 质量债已经归档为 superseded，不再作为 open product bug 跟踪。

## 当前 Open Bugs

- [009-specialization-prone-m29-internal-asset-gates.md](open/009-specialization-prone-m29-internal-asset-gates.md)：M29 internal asset chain 已避免硬特化，但仍有 OCR-anchor evidence bias、confidence gate drift 和 anti-specialization guard 缺口。
- [003-text-replacement-rejects-ui-labels-on-low-complexity-cards.md](open/003-text-replacement-rejects-ui-labels-on-low-complexity-cards.md)：M12 replacement 对部分已 OCR 识别的 UI 文本仍判为 `complex_background`。

## Superseded Bugs

- [017-codia-like-beta-ui-role-detector-gap.md](archive/superseded/017-codia-like-beta-ui-role-detector-gap.md)：旧 Go Codia Beta / Codia-like tree 路径质量债。已被 [093 Editable Draft Layer Pipeline Rebuild](../plans/active/093-editable-draft-layer-pipeline-rebuild.md) 取代。

## 最近 Resolved Bugs

- [019-pencil-psdlike-raster-icon-truncation.md](resolved/019-pencil-psdlike-raster-icon-truncation.md)
- [018-pencil-textlayer-cjk-clipping.md](resolved/018-pencil-textlayer-cjk-clipping.md)
- [016-media-contained-long-control-label-preserved-as-raster.md](resolved/016-media-contained-long-control-label-preserved-as-raster.md)
- [015-bottom-tab-selected-icon-stays-non-ocr-foreground.md](resolved/015-bottom-tab-selected-icon-stays-non-ocr-foreground.md)
- [014-fragmented-internal-icon-fails-transparent-asset-gate.md](resolved/014-fragmented-internal-icon-fails-transparent-asset-gate.md)
- [011-finite-control-backgrounds-can-be-preserved-as-media.md](resolved/011-finite-control-backgrounds-can-be-preserved-as-media.md)
- [012-bottom-tab-icons-stay-diagnostic-inside-composite-media.md](resolved/012-bottom-tab-icons-stay-diagnostic-inside-composite-media.md)
- [013-dsl-visual-comparison-text-noise-dominates-gate.md](resolved/013-dsl-visual-comparison-text-noise-dominates-gate.md)
- [010-dsl-visual-comparison-text-renders-as-solid-bars.md](resolved/010-dsl-visual-comparison-text-renders-as-solid-bars.md)
- [008-fallback-off-dark-ui-white-collapse.md](resolved/008-fallback-off-dark-ui-white-collapse.md)
- [007-composite-media-outer-shell-duplicates-top-tab-text.md](resolved/007-composite-media-outer-shell-duplicates-top-tab-text.md)
- [006-missing-text-nodes-not-added-to-fallback-single-nodes.md](resolved/006-missing-text-nodes-not-added-to-fallback-single-nodes.md)
- [005-m2902-preview-hides-accepted-image-evidence.md](resolved/005-m2902-preview-hides-accepted-image-evidence.md)
- [004-icon-gap-multiple-blocked-hints-fail-validation.md](resolved/004-icon-gap-multiple-blocked-hints-fail-validation.md)

## Structure

- `open/`：未解决 bug。
- `resolved/`：已解决 bug。
- `archive/superseded/`：被架构方向取代、不再作为 open bug 跟踪的历史问题。
- `template.md`：bug 记录模板。

## Rules

修复 bug 前必须：

- 记录复现方式。
- 记录影响范围。
- 定位根因。
- 加回归保护。
- 写验证证据。

没有回归保护，不关闭 bug。无法自动化时必须解释原因。
