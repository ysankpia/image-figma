# ADR 0009: 用标准库 PNG Region Slicer 建 M7 基座

- 状态：accepted
- 日期：2026-05-16

## Context

M6 已经能根据真实 PNG 宽高生成整图 fallback DSL，但 Figma 里仍然只有一个大 fallback 图层。下一步如果直接上 AI/OCR，会把“识别”和“资产区域管理”两个问题混在一起，失败时很难判断是模型问题、裁切问题还是 Renderer 问题。

## Decision

M7 先实现 deterministic region slicer。后端使用 Python 标准库解析 PNG chunks、还原 scanline filters、裁切 header/content/bottom 三段 region，并生成独立 PNG asset。暂不引入 Pillow，暂不接 OCR/AI，暂不改插件协议。

如果 PNG 尺寸可读但 cropper 不支持格式，任务不失败，DSL 退回整图 fallback，并在 `meta.qualityFlags` 写入 `region_crop_unsupported`。

## Consequences

好处：

- 上传链路开始生成可单独替换的 fallback 区域。
- 不需要新增图像处理依赖。
- M7 问题边界清楚：只验证 metadata、裁切、资产、DSL。
- 后续 OCR/AI 可以逐步替换某个 region，而不是重写整页链路。

代价：

- 标准库 cropper 只支持常见 PNG 格式：bit depth `8`、RGB/RGBA、non-interlaced。
- 不支持格式会退回整图 fallback。
- M7 仍不产生可编辑文字或真实组件。
