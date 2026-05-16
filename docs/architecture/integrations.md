# 外部集成

v0.1 的集成必须少而直接。

## Figma

Figma Plugin API 用于：

- 接收插件 UI 消息。
- 创建 root Frame。
- 创建文本、形状、图片、线条和基础图标。
- 设置节点位置和样式。
- 将生成结果放到当前页面。

Renderer 只通过 Figma Plugin API 写图层，不调用后端。

## OCR

M9 已建立 OCR contract harness。M10 新增可选百度 PP-OCRv5 异步 OCR provider。当前仍不是完整 OCR 产品化。

```text
PNG -> text boxes
```

OCR 用于：

- 识别文字。
- 提供文字 bbox。
- 提供置信度。
- 合并文本块。

OCR 输出至少包含：

- `text`
- `bbox`
- `confidence`
- `lineId`
- `blockId`

价格、手机号、订单号、日期、金额、库存等敏感文本以 OCR 为准，AI 不应自由改写。

当前 M10 规则：

- 默认 `OCR_PROVIDER=fake`。
- 可选 `OCR_PROVIDER=baidu_ppocrv5`，调用百度 AI Studio `PP-OCRv5` 异步 OCR API。
- 不调用同步 OCR API。
- 不引入本地 PaddleOCR、RapidOCR 或 Apple Vision provider。
- OCR 输出只进入 DSL patch builder。
- patch 默认生成 hidden `candidate_text`，不做可见文字替换。
- 百度 token 只通过环境变量提供，不写入仓库。
- 百度失败只影响 OCR/patch 调试结果，不影响 fallback DSL。

## AI / CV

M8 已接入的是 visual primitive contract harness，不是完整 AI 还原。

AI / CV 用于：

- 提出非文字 UI visual primitive candidates。
- 提供 card、button background、icon、image、shape、divider 等候选 bbox。
- 后续辅助元素归属判断和 role 判断。

调用策略：

- 默认 `VISUAL_PRIMITIVE_PROVIDER=fake`，不调用外部模型。
- 只有 `VISUAL_PRIMITIVE_PROVIDER=openai` 时才调用 OpenAI。
- OpenAI provider 分 region 调用，最多 3 个 region。
- OpenAI 输出 structured JSON，不输出 DesignDSL。
- 模型输出必须经过 primitive validator。
- JSON 异常和模型失败只影响 primitives 查询结果，不影响 M7 DSL。

不允许：

- AI 直接生成 DSL 并交给 Renderer。
- AI 抄写完整文字内容。
- AI 失败导致上传主链路失败。

## DSL Patch

M9 DSL patch builder 用于把 OCR boxes 和 visual primitives 转为可验证 patch：

- 默认 `DSL_PATCH_MODE=debug`。
- `off` 返回 M7 base DSL。
- `debug` 返回带 hidden text candidates 的 enhanced DSL。
- `apply` 在 M9 保留但不做可见替换。
- patch 失败回退 base DSL。

## Storage

开发阶段使用本地文件系统。

生产阶段可升级对象存储和签名 URL，但 v0.1 不提前实现。

## Browser / DevTools

插件 UI 或本地 Web UI 可使用 Chrome DevTools MCP 做本地可视化验证。Figma 画布写入仍需要 Figma 插件环境验证。
