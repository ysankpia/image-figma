# ADR 0021: Use Layer Separation Candidates Before Asset Slicing

- 状态：accepted
- 日期：2026-05-17

## Context

M17 已经把 M16 component/group 结构挂回 DSL element 的 `name` 和 `meta`，后端现在能追踪 OCR text、replacement cover、hidden candidate text、component 和 group 的关系。

下一步如果直接切图、删除局部 fallback 或做 componentization，风险仍然太高。不同 component 的分层策略不同：有些按钮和 badge 可以用 shape + editable text，有些卡片需要先判断文字下面能否简单填充，有些复杂图片必须 future repair 或保留 embedded text。

## Decision

M18 先生成 component-aware layer separation candidate 报告：

- 新增 `LayerSeparationDocument v0.1`。
- 新增 `/api/tasks/{taskId}/layer-separation-candidates`。
- 新增 `layer_separation_results` 索引表。
- 默认开启 `LAYER_SEPARATION_ENABLED=true`，因为它不改变 Figma 可见输出。
- 只消费 M14/M15/M16/M17 facts 和已有标准库 PNG sampling。
- 第一版只生成 `solid_color_fill` simple fill candidate，不生成实际切片或修复图。
- DSL 只追加顶层 M18 meta，不修改已有 element。

## Consequences

M19 可以基于 M18 报告选择低风险 component 做 local asset slice + simple fill 实验，而不是盲目裁图。

M18 不解决图标、圆形、三角形、五角星、复杂图形重建，不做 AI inpainting，不删除 fallback，不创建真实 Figma group/component，也不引入 Pillow/OpenCV。
