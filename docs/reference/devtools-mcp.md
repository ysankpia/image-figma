# DevTools MCP

Chrome DevTools MCP 是本地浏览器验证工具，不是 CI 替代品。

## Purpose

用于后续验证：

- 插件 UI 的本地开发页。
- 上传、预览、进度、完成、失败状态。
- 控制台错误。
- 网络请求。
- 页面布局问题。

## Not A CI Replacement

必须保留确定性测试：

- unit。
- integration。
- e2e。
- contract。

DevTools MCP 帮助 agent 看真实浏览器行为，但不能代替可重复执行的测试。

## Figma Limitation

Figma 画布写入行为需要在 Figma 插件环境验证。DevTools MCP 只能覆盖浏览器可见 UI 和网络行为。
