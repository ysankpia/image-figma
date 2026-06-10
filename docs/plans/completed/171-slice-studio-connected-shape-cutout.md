# 171 Slice Studio Connected Shape Cutout

- 状态：completed
- 创建日期：2026-06-11
- 负责人：Codex

## Goal

修复 `apps/slice-studio` 透明底裁切把深色按钮内部内容误删的问题。透明底模式应优先删除与裁剪框外边缘连通的外部背景，保留被图形轮廓包住的内部文字、图标和填充。

## Scope

包含：

- `apps/slice-studio/server/shape-cutout.ts` 透明底算法。
- `apps/slice-studio/tests/shape-cutout.test.ts` 回归测试。
- 针对用户提供导出样例做本地对比验证。

不包含：

- AI、OCR、YOLO、Pencil、Figma 自动复刻。
- 多对象实例分割，例如从同一个 bbox 里自动拆出 `Last Login` 和主登录按钮。
- SVG 矢量化。
- 导出 ZIP 结构、manifest schema、前端 UI 大改。

## Current Problem

当前 shape cutout 使用单一背景色距离阈值全图扣除像素。深色按钮内部颜色接近边缘背景时，算法会把按钮内部填充和文字周围内容一起透明掉。用户样例中透明模式三个 slice 的中心区域透明比例达到 58% 到 78%，说明它不是只去外部背景。

## Steps

1. 将 shape 模式从“全图颜色删除”改为“边缘连通背景删除”。
2. shape 模式在原图上临时扩展 bbox 做算法上下文，最终仍裁回用户原 bbox 尺寸。
3. 只把从扩展裁剪区边缘 flood-fill 连通到的背景候选设为透明。
4. 内部不与边缘连通的像素保持原 alpha，避免文字、图标、按钮填充被误删。
5. 添加深色背景、内部浅色内容、紧框扩裁的测试。

## Acceptance

- 矩形导出行为不变。
- shape 模式 PNG 仍为用户 bbox 尺寸。
- 深色按钮内部文字和图标不再被全图颜色阈值误删。
- 对明显失败的 mask 继续回退矩形，不中断导出。
- 用户样例中大按钮透明比例显著低于旧算法，中心区域不再大面积透明。

## Validation

- `cd apps/slice-studio && bun run test -- tests/shape-cutout.test.ts`
- `cd apps/slice-studio && bun run check`
- 用用户提供的两个导出目录生成 before/after 对比图。
- `git diff --check`

## Notes

紧贴目标的 bbox 仍然缺少外部背景信息。第一版通过临时扩裁提供上下文，但无法解决一个 bbox 内多个对象的语义拆分。`Last Login` 与主按钮叠在同一 bbox 时，是否拆分应交给后续 OCR/AI 候选或人工单独画框，不放进本轮透明底算法。
