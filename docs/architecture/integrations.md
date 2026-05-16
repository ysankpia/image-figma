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

## AI / CV

AI / CV 用于：

- 结构理解。
- 元素归属判断。
- role 判断。
- fallback 判断。
- 辅助生成 DSL。

调用策略：

- 普通页面最多 1 次主 AI 调用。
- JSON 异常最多 1 次 repair。
- 不做多轮模型流水线。

## Storage

开发阶段使用本地文件系统。

生产阶段可升级对象存储和签名 URL，但 v0.1 不提前实现。

## Browser / DevTools

插件 UI 或本地 Web UI 可使用 Chrome DevTools MCP 做本地可视化验证。Figma 画布写入仍需要 Figma 插件环境验证。
