# M12 Text Replacement Coverage Expansion

- 状态：active
- 创建日期：2026-05-17
- 负责人：Codex

## Summary

M12 在 M11 低风险文字替换基座上扩大可编辑文本覆盖率。它继续保留 fallback region、hidden OCR candidate 和 original reference，只在 `TEXT_REPLACEMENT_MODE=apply` 时追加 cover shape + visible text。

M12 不是完整可编辑还原，不做组件化、Auto Layout、图标识别、fallback 删除或 AI 结构理解。

## Key Changes

- replacement decision 继续使用 `TextReplacementDocument v0.1` 和 `GET /api/tasks/{taskId}/text-replacements`。
- 新增彩色/深色纯背景上的浅色文字接受路径，支持 `dark_or_colored_background_light_text` 和 `solid_colored_background`。
- 新增 foreground text color sampling，cover 使用采样背景色，visible text 使用采样文字色。
- visible text 显式设置 `fontFamily`、`fontSize`、`lineHeight` 和 `textAlign`，字号同时受高度、宽度和字符宽度约束，避免短中文 bbox 换行裁切。
- 增加最小 OCR block 合并：同一行、间距小、形态接近的拆分 block 可合并成一个 replacement candidate，原始 OCRDocument 不改。
- 新增配置：`TEXT_REPLACEMENT_ENABLE_COLORED_BG`、`TEXT_REPLACEMENT_MIN_CONTRAST`、`TEXT_REPLACEMENT_EDGE_SAMPLE_PADDING`、`TEXT_REPLACEMENT_TEXT_SAMPLE_INSET`。

## Test Plan

必须通过：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

覆盖点：

- 浅色纯背景黑字继续 accepted。
- 蓝色/深色纯背景白字 accepted。
- 低对比、复杂背景、无稳定前景色、安全框不足等路径 rejected。
- `TEXT_REPLACEMENT_ENABLE_COLORED_BG=false` 时彩色背景不 accepted。
- 短中文 bbox 不换行裁切，visible text 设置 `lineHeight`。
- 同行拆分 OCR block 可合并，不相关短标签不合并。
- `debug` 不改变 `/dsl` 可见输出，`apply` 保留 fallback/original/hidden candidate 并追加 cover/text。

## Assumptions

- 默认仍是 `TEXT_REPLACEMENT_MODE=debug`。
- M12 只扩大低复杂度背景文字替换覆盖率。
- 不引入 Pillow、OpenCV、PaddleOCR 或 RapidOCR。
- 不改 Figma 插件 UI/Main。
- 不删除、不裁切 fallback region。
