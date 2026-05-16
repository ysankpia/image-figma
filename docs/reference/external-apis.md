# 外部 API

当前仓库默认不调用外部 API。M8 增加了可选 OpenAI provider，只有显式设置 `VISUAL_PRIMITIVE_PROVIDER=openai` 时才会调用。

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

当前可选：

- OpenAI Responses API。

默认关闭：

```text
VISUAL_PRIMITIVE_PROVIDER=fake
```

启用 OpenAI smoke：

```text
VISUAL_PRIMITIVE_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_VISION_MODEL=gpt-5.5
```

要求：

- 支持结构化输出。
- 有超时。
- 有错误码。
- 输出不能直接作为 DSL。
- 输出 bbox 必须经过统一 validator。
- 失败不得影响 deterministic DSL 主链路。

## Storage Provider

v0.1 使用本地文件系统。

后续可接：

- OSS。
- S3 兼容对象存储。
- 签名 URL。
