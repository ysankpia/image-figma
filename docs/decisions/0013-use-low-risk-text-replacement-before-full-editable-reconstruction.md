# ADR 0013: Use Low-risk Text Replacement Before Full Editable Reconstruction

- 状态：accepted
- 日期：2026-05-16

## Context

M10 已经能用百度 PP-OCRv5 产生真实 OCR blocks。直接把所有 OCR text 变成可见 Figma Text 会造成双层文字，因为 fallback 图片中原文字仍然存在。完整解决需要背景重建、细粒度裁切和结构理解，不能混进第一版真实 OCR 接入。

## Decision

M11 先实现低风险可见文字替换 harness：

- 默认 `TEXT_REPLACEMENT_MODE=debug`，只保存 replacement decisions。
- `TEXT_REPLACEMENT_MODE=apply` 只处理浅色纯色背景、高置信 OCR block。
- accepted block 生成 cover shape 和 visible text。
- fallback region、original reference 和 hidden candidate text 全部保留。
- replacement 失败或校验失败时 `/dsl` 回退 M10/M9 输出。

## Consequences

好处：

- 可以开始验证真实文字可编辑性。
- 不会让复杂背景和双层文字拖垮整页。
- 每个 OCR block 的接受/拒绝原因可查询。

代价：

- 第一版只替换少量浅底文字。
- 深色按钮、图片背景、渐变区域和复杂布局仍保持 fallback。
- 字体、颜色、字重不做精确还原。

## Non-Goals

- 不做完整可编辑还原。
- 不删除 fallback region。
- 不做背景擦除模型。
- 不做 Auto Layout。
- 不让 OCR/AI 直接成为 DSL 权威。
