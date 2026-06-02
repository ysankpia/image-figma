# 101 PSD-like V1 Media Text Ownership And Layout Fit

- 状态：completed
- 创建日期：2026-06-02
- 完成日期：2026-06-02
- 所属链路：`services/backend-python` PSD-like V1 experiment

## Summary

Plan 100 已把按钮、标签、输入框这类有限控件背景从 raster 裁图路线拉回 `ShapeLayer + OCR TextLayer`。本计划继续修复最新 v6 人工抽查中暴露的另一层问题：**不是所有 OCR 文本都应该成为普通 UI TextLayer，也不是所有文本都能用固定字号估算渲染**。

目标仍然是：

```text
PNG -> 可快速编辑、可辅助开发的 Figma Draft
```

本轮只改 `services/backend-python` PSD-like V1，不继续 V2/V3，不接 YOLO/VLM，不改 HTTP API，不改变输出文件名。

第一原则：

```text
UI 文本                  -> OCR TextLayer，必须 fit bbox，不得撑爆布局
按钮/标签/输入框背景      -> ShapeLayer，文字在上层
照片/地图/banner/封面/装修图 -> RasterLayer，内部文字默认属于媒体内容
媒体内部 OCR 文本         -> 不应强行作为普通 UI TextLayer 覆盖 raster
```

## Evidence

最新完整产物：

```text
/Users/luhui/Downloads/psd_like_v1_control_surface_repair_eval_v6
```

用户点名抽查 case：

```text
case_0016_29094ac707
case_0041_83c0a7573a
case_0073_d923e89039
case_0078_e4388a0954
case_0081_f01eb628f1
case_0086_feef3bdc8d
```

当前判断：

```text
case_0016: 文字渲染过大/溢出，推荐区和封面区域文字 ownership 混乱
case_0041: 大体可用，剩余 knockout 来自房源卡片/媒体块
case_0073: 地图/marker/道路名属于 media/map text ownership 问题
case_0078: 大推荐卡 raster 覆盖 9 个 OCR 文本块，视觉接近但编辑语义不清
case_0081: 暗色页面 control surface recall 不足，部分按钮/卡片未矢量化
case_0086: 指标干净，无必须修的 ownership 问题
```

## Key Changes

### Stage 1: Text Layout Fit

当前 TextLayer 的字号主要从 OCR bbox 高度估算，缺少真实 fit。新增通用 text style 求解：

```text
OCR bbox + text
-> estimate target font size
-> measure rendered text
-> shrink until width/height fit bbox constraints
-> output fontSize/lineHeight/fit diagnostics
```

约束：

```text
不按文案、品牌、case、固定坐标分支
不把 hero/title/card 等语义写死成结构权威
只根据 bbox、文本长度、行数、局部尺寸、画布尺度做通用 fit
```

验收：

```text
case_0016 中大字撑爆明显下降
全量 86 图 TextLayer count 不下降，DSL 仍 valid
visualMae 不能系统性变差
```

### Stage 2: Media / Map Text Ownership

给大 media/map/photo/banner/complex raster 建立“内部文字归属”策略：

```text
large media raster containing OCR text
-> OCR block 标记为 media_owned_text
-> 不输出普通 TextLayer，或输出为 diagnostic/hidden metadata（本轮优先不输出 visible TextLayer）
-> 该 raster 不做 text knockout/inpaint
```

第一版只通过通用物理证据判断 media text：

```text
raster 面积足够大
raster texture/edge/entropy 较高
raster 覆盖多个 OCR block 或覆盖地图/图片式区域
OCR block 大部分落在 raster 内
该 raster 不是 accepted control surface
```

禁止：

```text
不按地图、房源、装修、账单等业务名判断
不按截图路径/文件名/case 编号判断
不按文案判断
不把所有大 raster 内文字都删掉；低纹理 UI 卡片仍应保留 UI TextLayer
```

验收：

```text
case_0073 地图内文字/marker 的重影和错误 TextLayer 减少
case_0078/0081 大媒体块内部文字 ownership 更稳定
普通按钮/表单/列表 UI 文字 TextLayer 不被误吞
```

### Stage 3: Dark Surface Control Recall

补暗色主题下的 control surface 检测。当前浅色按钮较好，暗色页面中低对比按钮/卡片可能因为 outer ring delta 不足被拒绝。

通用规则：

```text
dark local background
-> 使用 luminance delta + fill stability
-> 允许更弱 outer ring
-> 仍要求 padding、低纹理、OCR containment、有限尺寸
```

验收：

```text
case_0081 controlSurfaceShapeLayerCount 上升或明显暗色控件被 shape 接管
不误把大暗色 card/background/照片变成 control surface
```

### Stage 4: Reporting And Audit

增强 batch/diagnostics：

```text
textFitShrinkCount
mediaOwnedTextBlockCount
mediaTextOwnerRasterCount
darkControlSurfaceCount
visibleTextLayerCount vs ocrTextCount
```

保持所有 suppress/consume 决策可追溯：

```text
sourceTextBlockId
ownerRasterId
decisionReason
coverage/ratio
```

## Test Plan

### Unit Tests

新增或更新 `services/backend-python/tests/test_psd_like_experiment.py`：

```text
1. 长标题/中文书名 TextLayer font size 必须 fit bbox，不撑爆
2. 短文本按钮不被过度缩小
3. 多行 OCR 文本保持可读，不溢出 bbox
4. 大高纹理 media raster 内多个 OCR block -> media-owned，不输出普通 visible TextLayer
5. 普通低纹理 UI 列表文字不被 media policy 吞掉
6. media-owned raster 不做 text knockout/inpaint
7. 暗色低纹理按钮 + OCR -> dark control ShapeLayer + TextLayer
8. 大暗色背景/card 不被误判为有限 control surface
9. media/control/text decisions 在 rejected/diagnostics 中可审计
```

### Targeted Cases

先跑点名 case：

```text
case_0016_29094ac707
case_0041_83c0a7573a
case_0073_d923e89039
case_0078_e4388a0954
case_0081_f01eb628f1
case_0086_feef3bdc8d
```

### Full Batch

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/backend-python
uv run pytest -q tests/test_psd_like_experiment.py
uv run pytest -q
python -m py_compile tools/psd_like_layer_decomposition_experiment.py tools/psd_like_batch_eval.py app/*.py
uv run python tools/psd_like_batch_eval.py \
  --input-dir /Users/luhui/Downloads/测试 \
  --out /Users/luhui/Downloads/psd_like_v1_media_text_layout_fit_eval \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test
```

Hard gates:

```text
86/86 不崩
DSL valid = 86/86
missingAssetCount = 0
fullPageVisibleRaster = 0
shapeAssetCount = 0
TextLayer 不得覆盖同区域 media-owned raster 形成重影
media-owned text decisions 可审计
```

Quality gates:

```text
case_0016 大字撑爆明显下降
case_0073 地图/marker 文字重影下降
case_0081 暗色 control surface recall 提升
rawTextOverlapRaster 不上升
rasterTextKnockoutCount 不上升
avg visualMae 不系统性变差
最差 regression case 写入报告
```

## Assumptions And Boundaries

- 只修 PSD-like V1。
- 不改 HTTP API。
- 不接 YOLO、VLM、M29、Go backend。
- 不继续 V2/V3。
- 不做 Auto Layout、组件识别、Codia tree、SVG/Potrace。
- 不按样本名、路径、文案、品牌、固定 bbox、固定坐标、固定屏幕尺寸写规则。
- 如果 media text policy 误吞普通 UI 文本，回退或收紧，不靠样本例外修。

## Implementation Result

已完成：

```text
Text Layout Fit
-> TextLayer style 在 layer stack 阶段基于 OCR bbox + 字体测量求解
-> 记录 rawFontSize/fontSize/lineHeight/shrink/measuredWidth/measuredHeight
-> HTML preview 使用 style.lineHeight，不再把 line-height 强行撑成 bbox height

Media Text Ownership
-> complex media raster 内部 OCR block 可标记为 media_owned_text
-> media-owned text 不输出普通 visible TextLayer
-> raster asset 裁切只对 visible OCR text 做 knockout/inpaint
-> 小型 badge/icon/封面类 raster 支持内部文字 ownership，但宽按钮类 raster 不走该路径

Dark Control Surface Recall
-> 暗色、低纹理、高 fill stability 的 OCR-anchored control surface 允许较弱 outer ring
-> 仍保留有限尺寸、padding、文本 containment、texture/entropy/edge 与 text contrast 约束

Diagnostics
-> batch/diagnostics 增加 visibleTextLayerCount、mediaOwnedTextBlockCount、
   mediaTextOwnerRasterCount、textFitShrinkCount、darkControlSurfaceCount
```

反特化边界：

```text
实现只使用 source pixels、OCR bbox/text/confidence、relative geometry、
local color/edge/texture/entropy/fill stability、candidate reason。
未使用样本名、路径、可见文案、品牌、固定坐标、固定 bbox 或固定屏幕尺寸规则。
```

## Validation Result

Commands:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/backend-python
uv run pytest -q tests/test_psd_like_experiment.py
uv run pytest -q
python -m py_compile tools/psd_like_layer_decomposition_experiment.py tools/psd_like_batch_eval.py app/*.py
uv run python tools/psd_like_batch_eval.py \
  --input-dir /Users/luhui/Downloads/测试 \
  --out /Users/luhui/Downloads/psd_like_v1_media_text_layout_fit_eval_v2 \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test
git diff --check
```

Results:

```text
tests/test_psd_like_experiment.py: 39 passed
backend-python pytest: 80 passed
py_compile: passed
git diff --check: passed
86-image batch: 86/86 succeeded
DSL valid: 86/86
missingAssetCount: 0
fullPageVisibleRaster: 0
shapeAssetCount: 0
failureCaseCount: 0
```

Compared with Plan 100 v6 output `/Users/luhui/Downloads/psd_like_v1_control_surface_repair_eval_v6`:

```text
rawTextOverlapRaster: 38 -> 36
rasterTextKnockoutCount: 135 -> 54
rasterCoveredTextBlockCount: 327 -> 64
assetCount: 2269 -> 2265
textLayerCount: 6327 -> 6073
mediaOwnedTextBlockCount: 0 -> 254
avg visualMae: 10.4871 -> 10.0783
avg visualDiff30Ratio: 0.0698 -> 0.0665
```

Pointed case results:

```text
case_0016_29094ac707:
  textFitShrinkCount=36, rasterTextKnockoutCount 2 -> 1, visualMae 14.7069 -> 13.5782
  text_0009 rawFontSize 64 -> fontSize 19

case_0041_83c0a7573a:
  mediaOwnedTextBlockCount=2, darkControlSurfaceCount=6,
  rasterTextKnockoutCount 4 -> 2, visualMae 11.7760 -> 11.4991

case_0073_d923e89039:
  mediaOwnedTextBlockCount=2, rasterTextKnockoutCount 2 -> 0,
  rasterCoveredTextBlockCount 2 -> 0, visualMae 12.5191 -> 11.8317

case_0078_e4388a0954:
  mediaOwnedTextBlockCount=9, rasterTextKnockoutCount 1 -> 0,
  rasterCoveredTextBlockCount 9 -> 0, visualMae 9.0318 -> 8.0826

case_0081_f01eb628f1:
  mediaOwnedTextBlockCount=3, darkControlSurfaceCount=1,
  rasterTextKnockoutCount 2 -> 0, visualMae 12.0252 -> 11.6990

case_0086_feef3bdc8d:
  no ownership regression, visualMae 12.5235 -> 11.9725
```

Artifacts:

```text
/Users/luhui/Downloads/psd_like_v1_media_text_layout_fit_eval_v2/summary.json
/Users/luhui/Downloads/psd_like_v1_media_text_layout_fit_eval_v2/summary.md
/Users/luhui/Downloads/psd_like_v1_media_text_layout_fit_eval_v2/source_vs_draft_contact_sheet.png
/Users/luhui/Downloads/psd_like_v1_media_text_layout_fit_eval_v2/draft_preview_contact_sheet.png
/Users/luhui/Downloads/psd_like_v1_media_text_layout_fit_eval_v2/overlay_contact_sheet.png
```

## Remaining Risk

`rawTextOverlapRaster` 仍有 36 个，主要是很小的 foreground objects、图标角标、商品/封面局部和少量高纹理文字贴片。当前修复已把可明确归属的 text/media ownership 降下来，但没有为了指标删除可见图像内容。后续如果继续降 `rawTextOverlapRaster`，应做更明确的 pixel ownership classifier 或局部 mask/vector split，而不是继续扩大 media-owned text 的范围。
