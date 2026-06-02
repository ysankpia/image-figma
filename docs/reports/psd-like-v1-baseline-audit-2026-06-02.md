# PSD-like V1 Baseline Audit 2026-06-02

## Conclusion

PSD-like V1 当前已经可以作为可用 baseline。硬门全部通过，主要剩余问题不是同一种缺陷，而是截图反推设计稿时不可避免的 ownership 歧义：图标角标、商品图、地图、头像、封面、badge 内部文字经常会被 OCR 识别，但这些文字应该继续属于 raster，不应为了把指标清零而强拆成普通 `TextLayer`。

本次只修了一个确认可泛化的问题：**OCR-anchored control surface 的底色采样方式错误**。旧逻辑从整个候选 bbox 取主色，圆角按钮外侧或复杂卡片父背景会抢走按钮底色，导致浅色按钮、蓝色按钮或深色卡片里的按钮被拒。新逻辑改成从 OCR bbox 左右邻近 support pixels 优先取控件底色，再用局部边界证据验证 surface。

这不是黑色卡片特化，不依赖样本名、路径、文案、品牌、固定坐标或固定 bbox。

## Evidence

Baseline before this stage:

```text
commit: 88a870e fix: repair psd-like v1 media text ownership
output: /Users/luhui/Downloads/psd_like_v1_media_text_layout_fit_eval_v2
```

Output after this stage:

```text
/Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval
```

Visual audit sheets:

```text
/Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/source_vs_draft_contact_sheet.png
/Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/focused_old_new_preview_overlay.png
/Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/remaining_issue_contact_sheet.png
```

## Metrics

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| cases | 86 | 86 | 0 |
| failed cases | 0 | 0 | 0 |
| DSL valid | 86 | 86 | 0 |
| missingAssetCount | 0 | 0 | 0 |
| fullPageVisibleRaster | 0 | 0 | 0 |
| shapeAssetCount | 0 | 0 | 0 |
| rawTextOverlapRaster | 36 | 32 | -4 |
| rasterTextKnockoutCount | 54 | 52 | -2 |
| rasterCoveredTextBlockCount | 64 | 62 | -2 |
| assetCount | 2265 | 2218 | -47 |
| controlSurfaceShapeLayerCount | 241 | 517 | +276 |
| ocrAnchoredControlSurfaceCount | 209 | 486 | +277 |
| controlOwnedRasterSuppressedCount | 48 | 96 | +48 |
| darkControlSurfaceCount | 75 | 197 | +122 |
| avg visualMae | 10.0783 | 9.9612 | -0.1171 |
| avg visualDiff30Ratio | 0.0665 | 0.0656 | -0.0009 |
| max visualMae | 17.0652 | 18.1106 | +1.0454 |

The max visualMae regression is `case_0052_a6cbbd0038`. Focused inspection did not show media/photo deletion or a full-page backing regression; it is mainly caused by more small UI surfaces being vectorized. The average metrics and hard gates improved.

## Fixed Class

Fixed class:

```text
OCR text sits on a finite control surface,
but the old whole-bbox dominant color is stolen by surrounding parent background.
```

Example:

```text
case_0068_ca3aaed3a5
before: controlSurfaceShapeLayerCount=1, assetCount=42, knockout=1, coveredText=1
after:  controlSurfaceShapeLayerCount=5, assetCount=39, knockout=0, coveredText=0
```

The important implementation change is:

```text
OCR bbox
-> sample left/right support pixels near the text first
-> infer control fill from those support pixels
-> verify fill stability, contrast, finite size, and outer boundary support
-> emit ShapeLayer + OCR TextLayer
```

This handles light buttons on dark cards, blue buttons, yellow buttons, and pill controls through the same physical evidence.

## Remaining Issues

The remaining issue contact sheet shows these categories:

```text
1. icon/badge/status text:
   red notification numbers, battery percentage, dates, star icons, small app badges.

2. media/internal text:
   product labels, food photo labels, avatar badges, poster/cover text, map road names.

3. OCR/raster bbox edge contact:
   small overlaps where the raster and OCR box touch but the visible result is acceptable.

4. blue function tile/icon-like controls:
   e.g. some "智能诊断" style function tiles. These are not the same as finite button backgrounds;
   fixing them safely would require a separate icon-tile/vectorization policy.
```

Categories 1-3 are not worth fixing now. Category 4 can be a later P1, but it should not block this baseline.

## Decision

Freeze this V1 as the current Python PSD-like baseline.

Do not continue chasing:

```text
rawTextOverlapRaster = 0
rasterTextKnockoutCount = 0
all OCR text as visible TextLayer
all button-like pixels as shape
```

These targets would delete valid raster content or create false editability.

Next valuable work is integration readiness: expose or connect this stable baseline to a usable preview/import flow so real editing cost can be tested.

## Validation

Commands run:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/backend-python
uv run pytest -q tests/test_psd_like_experiment.py
uv run pytest -q
python -m py_compile tools/psd_like_layer_decomposition_experiment.py tools/psd_like_batch_eval.py app/*.py
uv run python tools/psd_like_batch_eval.py \
  --input-dir /Users/luhui/Downloads/测试 \
  --out /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test
```

Results:

```text
tests/test_psd_like_experiment.py: 40 passed
backend-python pytest: 81 passed
py_compile: passed
86-image batch: 86/86 succeeded
DSL valid: 86/86
missingAssetCount: 0
fullPageVisibleRaster: 0
shapeAssetCount: 0
```
