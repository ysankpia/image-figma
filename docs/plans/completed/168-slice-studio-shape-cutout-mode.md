# 168 Slice Studio Shape Cutout Mode

## Summary

给 Slice Studio 增加一个可试用的透明形状裁切模式。默认仍是稳定的矩形裁切；用户在 Review 里对单个 slice 打开“透明形状”后，导出时后端在该 bbox 内基于像素估计背景并生成 alpha mask，输出透明 PNG。

## Scope

- `apps/slice-studio` 数据合同、SQLite、导出、Review UI、smoke、测试、README。
- 不做 SVG 矢量化。
- 不接 AI/OCR/YOLO/Pencil/Figma。
- 不新增 HTTP API。

## Behavior

- `cutMode = rect | shape`，默认 `rect`。
- Review active asset 面板提供“透明形状”开关，资产列表显示透明标记。
- 保存 slices 时持久化 `cutMode`。
- 导出时：
  - `rect` 继续 `sharp.extract().png()`。
  - `shape` 先裁 bbox，再根据四角/边缘估计背景，生成 alpha mask，输出透明 PNG。
- 算法失败或区域太小，仍输出原裁图，不中断导出。

## First Version Algorithm

- 采样 bbox 四角和边缘像素估计背景色。
- 计算每个像素到背景色的 RGB 距离。
- 距离超过阈值则作为前景。
- 边缘轻微羽化。
- 输出 RGBA PNG。

## Validation

- `cd apps/slice-studio && bun run check`
- `cd apps/slice-studio && bun run build`
- `cd apps/slice-studio && bun run smoke`
- 测试透明裁切输出含 alpha 通道。
- 浏览器验证开关可保存，导出正常。
- `git diff --check`
