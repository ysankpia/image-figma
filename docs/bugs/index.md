# Bug Ledger

本目录记录 shipped bug、根因、修复和回归保护。

当前 open bug：

- [003-text-replacement-rejects-ui-labels-on-low-complexity-cards.md](open/003-text-replacement-rejects-ui-labels-on-low-complexity-cards.md)：M12 replacement 对部分已 OCR 识别的 UI 文本仍判为 `complex_background`。

最近 resolved bug：

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
