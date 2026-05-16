# 外部 API

当前仓库没有代码调用外部 API。本文件记录后续集成边界。

## Figma Plugin API

用途：

- 创建节点。
- 设置布局和样式。
- 加载图片。
- 写入当前页面。

约束：

- 只在 Plugin Main 或 Renderer 运行环境使用。
- 后端不得依赖 Figma Plugin API。

## OCR Provider

候选：

- PaddleOCR。
- 等价 OCR 服务。

输出必须标准化为 text、bbox、confidence、lineId、blockId。

## AI Provider

候选：

- OpenAI 视觉模型。
- 等价结构化视觉模型。

要求：

- 支持结构化输出。
- 有超时。
- 有错误码。
- 有调用摘要日志。

## Storage Provider

v0.1 使用本地文件系统。

后续可接：

- OSS。
- S3 兼容对象存储。
- 签名 URL。
