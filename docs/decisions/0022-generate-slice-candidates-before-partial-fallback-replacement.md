# ADR 0022: Generate Slice Candidates Before Partial Fallback Replacement

- 状态：accepted
- 日期：2026-05-17

## Context

M18 已经能判断 component 后续是否适合 shape + editable text、image slice with simple fill candidate、future repair 或 embedded text。但 M18 只输出 JSON 策略，不生成实际 PNG。

如果 M20 直接开始删除局部 fallback 或替换画布，失败会立刻影响 Figma 可见输出。更稳的顺序是先把可切片、可简单填充的 component 生成本地候选资产，让报告、资产文件和 DSL meta 建立闭环。

## Decision

M19 新增 local asset slice candidate harness：

- 新增 `AssetSliceCandidateDocument v0.1`。
- 新增 `/api/tasks/{taskId}/asset-slice-candidates`。
- 新增 `asset_slice_results` 索引表。
- 默认开启 `ASSET_SLICE_ENABLED=true`，因为它不改变 Figma 可见输出。
- 只消费 M18 candidates 和原始 PNG，不重新理解图片语义。
- 使用现有标准库 PNG 工具，并补充最小 `encode_rgb_png` / `crop_and_fill_png` 能力。
- 不引入 Pillow/OpenCV。
- 生成的 slice PNG 写入本地 storage 和 `assets` 表，但不写进 DSL `assets` 数组。
- DSL 只追加顶层 M19 meta。

## Consequences

M20 可以基于 M19 报告和本地 slice 文件做 partial fallback replacement 实验，而不是盲目裁图。

M19 不解决正式局部 fallback 删除、组件化、Auto Layout、图标重建、复杂 shape 重建或 AI inpainting。失败的 slice 只进入报告，不影响 upload completed 和当前 Figma 可见输出。
