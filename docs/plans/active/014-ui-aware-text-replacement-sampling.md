# M14 UI-aware Text Replacement Sampling

- 状态：active
- 创建日期：2026-05-17
- 负责人：Codex

## Summary

M14 修复 M12/M13 前置采样层的 `complex_background` 误杀。OCR 已识别的 badge、legend、outline button、card/tip 和 bottom nav 文本，不应只因为标准 expanded-bbox perimeter sampling 采到色块、边框、阴影或少量图标像素就直接拒绝。

M14 不新增 OCR provider，不改百度 OCR，不改插件或 Renderer，不重建图标/组件/Auto Layout，不删除 fallback region，也不全局调大背景容差。

## Key Changes

- `TextReplacementDecision` 增加 `strategy` 字段，记录最终 sampling strategy 和全部 attempts。
- `TextReplacementDocument.meta` 增加 `samplingNotes`、`strategySummary` 和 `rescuedFromComplexBackgroundCount`。
- 新增配置：`TEXT_REPLACEMENT_UI_AWARE_SAMPLING`、`TEXT_REPLACEMENT_LOCAL_BG_TOLERANCE`、`TEXT_REPLACEMENT_MAX_RESCUE_STRATEGIES`。
- 标准 `standard_perimeter_sample` 仍先运行；只有 `complex_background`、`text_color_uncertain`、`foreground_background_low_contrast`、`dark_background` 等可救失败才尝试 rescue。
- 新增局部策略：`pill_inner_background_sample`、`legend_text_side_sample`、`outline_button_text_sample`、`card_local_background_sample`、`bottom_nav_label_sample`。
- `TEXT_REPLACEMENT_MODE=apply` 的 DSL merge 形状不变，仍追加 cover shape 和 visible text，并继续经过 M13 quality gate。

## Test Plan

必须通过：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

覆盖点：

- 标准浅色/彩色低复杂度背景仍 accepted。
- 真实复杂纹理背景仍 rejected，不能被 rescue。
- badge/status badge、legend 三标签、outline button、card/tip、bottom nav label 可从标准 `complex_background` 中被局部采样 rescue。
- `TEXT_REPLACEMENT_UI_AWARE_SAMPLING=false` 时保持 M13 行为。
- `strategy.attempts`、`meta.strategySummary`、`rescuedFromComplexBackgroundCount` 可解释采样路径。
- apply 仍保留 fallback region、original reference 和 hidden candidate text。

## Assumptions

- M14 默认仍是 `TEXT_REPLACEMENT_MODE=debug`，不会默认改变可见输出。
- M14 只解决“已 OCR 识别但被采样误杀”的一类问题。
- OCR 漏识别、图标组文字绑定、组件化、fallback 删除和 Auto Layout 进入 M15/M16 以后。
