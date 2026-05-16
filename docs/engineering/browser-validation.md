# 浏览器和插件验证

浏览器可见行为不能只靠代码阅读。

## Local Validation Path

后续存在本地 Web UI 或插件 UI 开发页时，优先使用 Chrome DevTools MCP 检查：

- 页面是否能打开。
- 控制台是否有错误。
- 网络请求是否符合预期。
- 上传、预览、进度、完成、失败状态是否可见。
- 文本是否溢出。
- 移动或窄宽度布局是否破坏。

Figma 画布写入行为必须在 Figma 插件环境验证：

- root Frame 是否生成。
- 图层尺寸是否正确。
- Text 是否可编辑。
- 图片是否加载。
- 失败是否能返回 UI。

## CI Validation Path

CI 应保留确定性测试：

- DSL schema 测试。
- Renderer 假 DSL 测试。
- API 集成测试。
- 插件 UI 状态测试。
- 关键 e2e 流程。

Chrome DevTools MCP 是本地 agent 反馈环，不替代 CI。

## Evidence

高风险 UI 或 Renderer 改动需要记录：

- 验证的样例。
- 验证环境。
- 关键截图或文字结果。
- 已知问题。
