# 100 PSD-like V1 Control Surface Ownership Repair

- 状态：completed
- 创建日期：2026-06-02
- 所属链路：`services/backend-python` PSD-like V1 experiment

## Summary

本计划直接修复 PSD-like V1，不继续 V2/V3，不接 YOLO，不改 HTTP API。目标是让按钮、标签、输入框这类带 OCR 文字的有限控件背景优先成为 `ShapeLayer`，OCR 文字保持独立 `TextLayer`，同一区域不再输出按钮整块 raster asset，也不对按钮文字做 inpaint。

核心合同：

```text
control background -> ShapeLayer with complete fill
control text       -> OCR TextLayer above shape
control raster     -> suppressed unless it is a real inner icon/photo foreground
```

## Key Changes

- 新增 OCR-anchored control surface 检测：只用 source pixels、OCR bbox、text mask、局部 fill/texture/outer-ring evidence，不从 text bbox 硬造背景。
- accepted control surface 拿到背景 ownership 后，重叠 raster/residual 被 suppress，写入 diagnostics/rejected artifact。
- `inpaint_text_pixels_in_raster()` 保留给非控件复杂 raster 兜底，但控件 surface 区域禁止走 inpaint。
- 强制 layer z-order：shape `10000+`、raster `20000+`、text `30000+`。
- 增加 text-owned raster fragment 抑制：只移除小/紧凑且高重叠 OCR 文本的 raster 碎片，不移除父级照片、banner 或复杂大图。
- `rejected` 导出优先保留 `control_owned_raster_suppressed` 和 `text_owned_raster_suppressed`，避免 diagnostics 计数与可审计明细不一致。
- batch summary 增加 `textOwnedRasterSuppressedCount` 和 `rasterCoveredTextBlockCount`，用于区分矩形重叠、真实文字像素 knockout 和 suppress 决策。

## Test Plan

```bash
cd services/backend-python
uv run pytest -q tests/test_psd_like_experiment.py
uv run pytest -q
python -m py_compile tools/psd_like_layer_decomposition_experiment.py app/*.py
uv run python tools/psd_like_batch_eval.py \
  --input-dir /Users/luhui/Downloads/测试 \
  --out /Users/luhui/Downloads/psd_like_v1_control_surface_repair_eval \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test
```

Hard gates: no crash, DSL valid, missing assets `0`, visible full-page raster `0`, accepted control surfaces have no raster asset, OCR text remains above same-region shape/raster.

Quality signals: lower `rasterTextKnockoutCount`, lower `rawTextOverlapRaster`, fewer button-like raster assets, fewer edge/shadow fragments, and no systematic visual MAE regression.

## Validation Result

Commands:

```bash
cd services/backend-python
uv run pytest -q tests/test_psd_like_experiment.py
uv run pytest -q
python -m py_compile tools/psd_like_layer_decomposition_experiment.py tools/psd_like_batch_eval.py app/*.py
uv run python tools/psd_like_batch_eval.py \
  --input-dir /Users/luhui/Downloads/测试 \
  --out /Users/luhui/Downloads/psd_like_v1_control_surface_repair_eval_v6 \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test
```

Results:

```text
tests/test_psd_like_experiment.py: 31 passed
backend-python pytest: 72 passed
py_compile: passed
86-image batch: 86/86 succeeded
DSL valid: 86/86
missingAssetCount: 0
fullPageVisibleRaster: 0
shapeAssetCount: 0
visible text overlap: 0
control/text suppress audit mismatches: 0
large text-owned suppressions: 0
```

Compared with `/Users/luhui/Downloads/psd_like_batch_eval_test_all` baseline:

```text
rawTextOverlapRaster: 53 -> 38
rasterTextKnockoutCount: 176 -> 135
assetCount: 2340 -> 2269
avg visualMae: 10.5639 -> 10.4871
max visualMae: 28.1969 -> 17.1098
controlSurfaceShapeLayerCount: 0 -> 198
ocrAnchoredControlSurfaceCount: 0 -> 166
controlOwnedRasterSuppressedCount: 0 -> 46
textOwnedRasterSuppressedCount: 0 -> 4
```

Anti-specialization check:

```text
No sample name, visible text, brand, fixed coordinate, fixed bbox, fixed screen size, or path-specific production rule was found.
```

## Remaining Risk

The remaining `rawTextOverlapRaster` and `rasterTextKnockoutCount` are mostly non-control raster regions such as foreground objects, photos, banners, or complex visual regions containing real OCR text. They are intentionally not suppressed by the control-surface path because doing so would delete useful image content. Future work should split true media text ownership from editable OCR text with a separate media/text policy rather than making control-surface suppression more aggressive.

## Assumptions

- V2/V3 remain untouched.
- First version supports solid fill + rounded rect only.
- No sample-name, visible-text, fixed bbox, fixed coordinate, fixed screen-size, brand, or theme special casing.
