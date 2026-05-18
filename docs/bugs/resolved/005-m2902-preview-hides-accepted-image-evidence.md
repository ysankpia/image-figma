# Bug: M29.0.2 preview hides accepted image evidence

- 状态：resolved
- 创建日期：2026-05-18
- 影响范围：M29.0.2 text-masked media audit preview/evidence crops

## Summary

M29.0.2 audit JSON 和 overlay 能记录 M29 accepted image，例如 hero/banner carousel `image_002`，但 `preview_text_masked_media_audit.png` 底部证据区没有展示这些 accepted image crops，导致人工验收时误以为轮播图被 M29.1 或 OCR 流程拆没了。

## Reproduction

1. 使用 Paddle OCR 运行 M29.0.2 smoke。
2. 查看 `text_masked_media_audit.json`，`m29_image_002 [23, 161, 808, 288]` 存在。
3. 查看 `preview_text_masked_media_audit.png`，顶部 overlay 有对应框，底部证据 crop grid 没有该图片。

## Root Cause

M29.0.2 的 `collect_media_evidence` 为 `m29_image` 和 `m291_group` 创建了 evidence item，但把 `asset_path` 设为 `None`。preview crop grid 只渲染有 `asset_path` 的 evidence，因此这些证据只出现在 JSON/overlay，不出现在底部 crop grid。

## Fix

`m29_image` 和 `m291_group` 现在也从原始 source PNG 导出 evidence crop：

```text
m29_image -> assets/accepted_images/*.png
m291_group -> assets/symbol_groups/*.png
```

这只修复 audit 展示层，不改变 M29/M29.1 detector、grouping、上传主链路、DSL 或 Figma 输出。

## Regression Guard

`backend/tests/test_text_masked_media_audit.py` 增加断言：`m29_image` 和 `m291_group` evidence 必须有可读 `asset_path`，且 crop 尺寸等于 bbox。

## Validation Evidence

```bash
cd backend && uv run pytest tests/test_text_masked_media_audit.py -q
```

结果：`5 passed`。

## Prevention Notes

M29.0.2 的人工验收对象是“可见证据”，不是单纯 JSON 记录。任何进入 `mediaEvidence` 且有 bbox 的视觉对象，除非明确是纯 metadata，否则都应该能在 preview grid 中看到对应 crop。
