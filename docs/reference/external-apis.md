# 外部 API

当前仓库默认不调用外部 API。M8 增加了可选 OpenAI primitive provider，只有显式设置 `VISUAL_PRIMITIVE_PROVIDER=openai` 时才会调用。M10 增加了可选百度 PP-OCRv5 异步 OCR provider，只有显式设置 `OCR_PROVIDER=baidu_ppocrv5` 且提供 token 时才会调用。

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

当前：

- `OCR_PROVIDER=fake`。
- `OCR_PROVIDER=baidu_ppocrv5`。

百度 PP-OCRv5：

- Endpoint 默认：`https://paddleocr.aistudio-app.com/api/v2/ocr/jobs`。
- Model 默认：`PP-OCRv5`。
- 鉴权：`Authorization: bearer <BAIDU_PADDLE_OCR_TOKEN>`。
- 只使用异步 jobs API，不接同步接口。
- 返回的 `rec_texts`、`rec_scores`、`rec_boxes`、`rec_polys` 会被标准化为 `OCRDocument v0.1`。

输出必须标准化为 text、bbox、confidence、lineId、blockId。

后续候选：

- PaddleOCR-VL-1.5 作为结构解析 provider。
- PP-StructureV3 作为文档结构 provider。
- 等价商业 OCR 服务。

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
