# 109 PSD-like Surface-Aware Text Style And Layout Repair

- 状态：completed
- 创建日期：2026-06-03
- 负责人：Codex

## Summary

本阶段修复 108 后剩下的按钮/背景内文字问题：

```text
背景已经能拆成 Shape/Raster
但 TextLayer 的颜色、字号、字重、字体和父背景关系不够接近原图
```

核心边界：

```text
108 修的是 control surface false-positive
109 修的是 TextLayer style/materialization
```

目标链路：

```text
PNG pixels
+ OCR text/bbox
+ confirmed/local owner surface
-> surface-aware text style
-> fixed Draft Runtime TextLayer
-> renderer loads matching Figma font style
-> Figma 可编辑文字尽量接近原图
```

本阶段允许改：

```text
services/psdlike-python
packages/image-to-figma-renderer
```

本阶段验证只跑：

```text
case_0036_764d3a58e5
case_0037_7aa443d6c7
case_0058_b048f93bd2
```

三图稳定后停止，不跑 86 全量。

## Key Changes

### Surface-aware Text Style

TextLayer 生成前建立 `text -> owner context`：

```text
confirmed control shape
local surface/container shape
nearby raster/media owner
page/local background
```

`estimate_text_style()` 从当前：

```text
rgb + OCR bbox + text
```

升级为：

```text
rgb + OCR bbox + text + optional TextStyleContext
```

没有 owner 时保持当前 fallback 行为，避免无关文本大漂移。

### Contrast-weighted Text Color

迁回历史 M36.1 的前景色原则：

```text
text bbox pixels
+ owner fill / local background RGB
-> foreground candidate pixels with sufficient contrast
-> RGB bucket
-> contrast + luminance polarity + capped sqrt(count) scoring
-> style.color
```

输出 diagnostics：

```text
textColorSource
textColorBackground
textForegroundScore
```

### Font Family / Weight / Harmonization

默认策略：

```text
CJK 文本 -> PingFang SC
拉丁/数字主文本 -> Inter
fontWeight 500 -> Medium
fontWeight 600 -> Semibold
fontWeight 700+ -> Bold
```

同排相似文本做字号 harmonization：

```text
同一行 y-center 接近
bbox 高度接近
fontSize 接近
角色/颜色接近
-> snap 到 row mode fontSize
```

### Owner-aware Control Text Box

确认 control surface 内的单行 label 不再直接使用 OCR 原始高度作为固定 Figma TextLayer bbox：

```text
OCR bbox + measured text size + owner control bbox
-> keep OCR horizontal evidence
-> center text bbox vertically in owner control surface
-> keep textAutoResize = NONE
```

这修复了固定 TextLayer 顶对齐导致的按钮文字视觉上偏上问题。

### Control-owned Shape Fragment Suppression

当普通低纹理 shape 与 confirmed control surface 高重叠、面积同量级、中心接近时，将其判定为 control-owned shape fragment 并从 visible shape candidates 中移除。

该规则只使用：

```text
confirmed control ownership
IoU / IoA
relative area
relative center distance
shape reason class
```

不使用 case id、固定坐标、固定 bbox、具体文案或品牌。

## Test Plan

Backend：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
python -m py_compile $(find app tools -name '*.py' | sort)
uv run pytest -q
```

Renderer：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
```

Targeted validation：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
rm -rf /Users/luhui/Downloads/psdlike_109_text_style_targeted
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_109_text_style_targeted \
  --case-id case_0036_764d3a58e5 \
  --case-id case_0037_7aa443d6c7 \
  --case-id case_0058_b048f93bd2
```

硬门：

```text
failed cases = 0
DSL valid = true for all 3
missingAssetCount = 0
shapeAssetCount = 0
fullPageVisibleRaster = 0
tinyRasterFragments = 0
108 targeted false-positive 不回归
```

## Assumptions

```text
不改 HTTP API
不改 Draft Runtime schema
不改 plugin UI/API client
不新增模型依赖
不使用 case id、路径、图片名、品牌、具体文案、固定坐标、固定 bbox、固定屏幕尺寸
Draft Runtime textAutoResize 保持 NONE
```

## Validation Evidence

代码检查：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
python -m py_compile $(find app tools -name '*.py' | sort)
uv run pytest -q
```

结果：

```text
39 passed, 1 warning
```

Renderer 检查：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
```

结果：

```text
typecheck passed
5 test files passed
19 tests passed
```

Targeted validation：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
rm -rf /Users/luhui/Downloads/psdlike_109_text_style_targeted
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_109_text_style_targeted \
  --case-id case_0036_764d3a58e5 \
  --case-id case_0037_7aa443d6c7 \
  --case-id case_0058_b048f93bd2
```

结果：

```text
cases = 3
failed cases = 0
DSL valid = true for all 3
missingAssetCount = 0 for all 3
shapeAssetCount = 0 for all 3
fullPageVisibleRaster = 0 for all 3
tinyRasterFragments = 0 for all 3
```

Targeted diagnostics：

```text
case_0036_764d3a58e5:
  modelAssistedMediaRasterCount = 0
  controlOwnedShapeSuppressedCount = 1
  textOwnerBboxRecenteredCount = 3
  "提现" region keeps one confirmed blue control surface and centered editable TextLayer.

case_0037_7aa443d6c7:
  textOwnerAwareColorCount = 101
  textRowHarmonizedCount = 12
  hard gates passed.

case_0058_b048f93bd2:
  controlOwnedShapeSuppressedCount = 1
  textOwnerBboxRecenteredCount = 4
  certificate control false positives from 108 remain blocked.
```

Artifact inspected:

```text
/Users/luhui/Downloads/psdlike_109_text_style_targeted/case_0036_764d3a58e5/draft_preview.png
/Users/luhui/Downloads/psdlike_109_text_style_targeted/case_0036_764d3a58e5/overlay.png
/Users/luhui/Downloads/psdlike_109_text_style_targeted/source_vs_draft_contact_sheet.png
```
