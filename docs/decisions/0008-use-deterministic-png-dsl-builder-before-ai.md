# ADR 0008: 先用 deterministic PNG DSL Builder 再接 AI

- 状态：accepted
- 日期：2026-05-16

## Context

M5 已经跑通插件上传、后端任务、DSL 获取和 Renderer 写入 Figma。但 M4 后端仍用固定 `mobile-home.dsl.json` 生成 DSL，上传不同 PNG 也会得到同一份页面结构。

## Decision

M6 先实现 deterministic PNG -> DSL Builder。后端读取真实 PNG 宽高，生成 root frame、隐藏原图参考层和整图 fallback 层。不在本轮接 OCR、AI、裁切或真实布局理解。

## Consequences

好处：

- 上传链路开始由真实输入驱动。
- 不需要模型密钥或新图像依赖。
- Renderer 能稳定显示任意 PNG 的完整 fallback。
- 后续 AI/OCR 可以在确定的 fallback 基线之上增量替换为可编辑元素。

代价：

- M6 还不能识别文字和组件。
- 输出主要是整图 fallback，不是最终可编辑稿。
