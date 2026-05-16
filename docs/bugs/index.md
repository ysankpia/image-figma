# Bug Ledger

本目录记录 shipped bug、根因、修复和回归保护。

当前项目还没有代码实现，因此没有 bug 记录。

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
