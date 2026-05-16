# 一期不做事项

本文档是硬边界。没有明确升级计划前，以下功能不得塞进 v0.1。

## Product Non-Goals

一期不做：

- 批量上传。
- 历史记录。
- 最近任务。
- 用户账号。
- 团队协作。
- 权限系统。
- 额度、计费、支付。
- 完整质量报告。
- 插件内原图和生成结果对比。
- 差异热力图。
- 多模型对比平台。
- 完整评分看板。
- 复杂用户教程。
- 开发者平台。

## Design And Figma Non-Goals

一期不做：

- 代码生成。
- 真正 Figma Component。
- Figma Instance。
- 一键组件化。
- Auto Layout 自动推断。
- Responsive Layout。
- Hug Content / Fill Container 推断。
- 完整设计系统还原。
- 复杂图标库。
- 完整 Assets 管理面板。

原因很简单：输入是 PNG，系统无法可靠知道设计师真实布局意图。强行推断只会把 MVP 拖进不可控复杂度。

## Recognition Non-Goals

一期不做：

- 多轮 AI 复杂分析。
- 自动低分修复闭环。
- 完整图表结构化。
- 复杂后台系统深度识别。
- Web / Landing Page 深度支持。
- 自动切长图为多个页面。
- 复杂图片重生成。

复杂区域可以 fallback。Fallback 是质量策略，不是失败。

## Engineering Non-Goals

一期不做：

- 微服务。
- 复杂队列系统。
- 复杂缓存系统。
- 正式商业化存储策略。
- 完整隐私合规系统。
- 生产级监控平台。
- 多租户隔离。

MVP 阶段优先本地文件存储、SQLite 和清晰日志。
