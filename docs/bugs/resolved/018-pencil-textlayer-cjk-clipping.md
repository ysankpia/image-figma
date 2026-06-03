# Bug: Pencil editable CJK TextLayer clipped by tight OCR bbox

- 状态：resolved
- 创建日期：2026-06-03
- 影响范围：`services/pencil-python-backend` 的 `clean-editable` 和 `visual-ocr` 输出

## Summary

`jianzhi-psdlike-boundary-realocr-v2` 的 page_0003 中，`今日提交数` 和
`今日完成数` 在 OCR、PSD-like layer stack 和最终 `.pen` 中都存在，但 Pencil
预览里文字有裁切风险。

## Reproduction

1. 打开 `/Volumes/WorkDrive/pencil-exports/jianzhi-psdlike-boundary-realocr-v2/clean-editable/design.pen`。
2. 查看 page_0003 的 `今日提交数` 和 `今日完成数`。
3. 对比 `work/page_0003/psdlike/input.ocr_blocks.v1.json`、`layer_stack.v1.json` 和最终 `.pen`。

## Root Cause

后端把 OCR bbox 原样作为 `.pen` TextLayer 的固定宽高：

```text
textGrowth: fixed-width-height
width/height: raw OCR bbox
fontFamily: system-ui
```

OCR bbox 本身很贴字。Pencil 实际 CJK 字体渲染与 Python 测量字体不同，
固定框没有安全余量时会裁切 glyph。

## Fix

在生成可见 OCR TextLayer 时使用通用 safe bounds：

- 宽高按字体大小和脚本类型扩出安全边界。
- x/y 反向移动以保持文字中心不变。
- 扩展后 clamp 到画布。
- font size 仍基于原始 OCR bbox fit，避免视觉尺寸被放大。

## Regression Guard

新增单元测试覆盖 CJK TextLayer：

- safe bounds 大于原始 OCR bbox。
- metadata 保留 original/safe bbox。
- 文本内容、fontSize、视觉中心保持稳定。

## Validation Evidence

- `cd services/pencil-python-backend && uv run python -m py_compile $(find app tests -name '*.py' | sort)`
- `cd services/pencil-python-backend && uv run pytest -q`
- Re-exported page_0003 from existing real-OCR Pencil evidence:
  `/Volumes/WorkDrive/pencil-exports/text-safe-bounds-page0003-single-20260603-222344`
- Pencil CLI preview:
  `/Volumes/WorkDrive/pencil-exports/text-safe-bounds-page0003-single-20260603-222344/preview/clean-editable.png`
- Focused source/old/new comparison:
  `/Volumes/WorkDrive/pencil-exports/text-safe-bounds-page0003-single-20260603-222344/preview/page_0003_metrics_fixed_compare.png`

## Prevention Notes

不要把 OCR bbox 当成 Pencil 文本渲染盒。OCR bbox 是视觉证据框，不是跨字体
编辑器的最终 layout bounds。
