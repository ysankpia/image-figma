# Slice Studio Dense Text Editable Policy

- 状态：completed
- 创建日期：2026-06-12
- 负责人：Codex

## Goal

让密集 PC UI 图中已经被 OCR 识别、并且被 M29/本地 foreground 定位的小字号文字直接生成 Pencil 可编辑文本层，而不是因为“密集页面小字”被一刀切保留为图片。

## Scope

包含：

- 删除 `tiny_dense_ui_text` 强制 raster-preserve 策略。
- 保留低置信 OCR、空文本、无效 bbox、生成标记标签、slice overlap、几何异常等现有保护。
- 增加回归测试，证明高置信 OCR + M29 foreground 的小字可以变成可编辑文本。
- 用真实 dense PC UI 项目导出验证 text layer 数量和 Pencil layout。

不包含：

- 不接入 UpscalerJS 或其他超分依赖。
- 不做整图超分。
- 不改 AI prompt、SQLite、storage、Pencil package schema、导出协议或前端 UI。

## Steps

1. 移除 `denseTextPage && bbox.height <= 10` 的 raster-preserve 判断。
2. 删除不再使用的 dense text page 计算。
3. 补充回归测试。
4. 运行 Slice Studio 检查。
5. 重新导出真实 dense PC UI 项目并用 Pencil 检查。

## Acceptance

- `tiny_dense_ui_text` 不再阻止高置信小字生成 text layer。
- `generated_asset_marker_label`、`ocr_text_inside_confirmed_slice`、`physical_text_inside_confirmed_slice` 仍然有效。
- 真实 dense PC UI 导出后 text layer 数量明显增加。
- Pencil layout 检查无问题。

## Validation

- `pnpm --dir apps/slice-studio exec vitest run tests/pencil-exporter.test.ts`
- `pnpm --dir apps/slice-studio run check`
- `git diff --check`
- `project_mqavhwm7_875518fe` 重新导出并检查 manifest / Pencil layout。
- `project_mqar9qpo_93b911d9` 重新导出并检查 manifest / Pencil layout。

## Notes

- 当前事实：`09-pc-platform-meta-template-regen-huaya-v2.png` 上 OCR/M29 已经能识别和定位大多数小字，原先主要阻塞是 `tiny_dense_ui_text` 策略。
- 超分/增强可以作为以后独立研究，但不是本轮主矛盾。
