# 103 PSD-like V1 Baseline Audit And Dark Control Recall

- 状态：completed
- 创建日期：2026-06-02
- 完成日期：2026-06-02
- 所属链路：`services/backend-python` PSD-like V1 experiment

## Goal

冻结当前 PSD-like V1 作为可用 baseline，并只修一个明确、可泛化的剩余问题：**暗色/复杂卡片里的按钮或标签背景漏召回**。

当前 V1 已经通过 86 图硬门：

```text
DSL valid = 86/86
missing asset = 0
visible full-page raster = 0
shape asset = 0
```

剩余问题不是单一 bug。大量 `rawTextOverlapRaster` 来自图标角标、商品图、地图、头像、封面或 badge 内部文字，这些应当保留为 raster ownership，不应继续为了指标清零而拆成普通 TextLayer。

## Scope

包含：

- 写当前 baseline 审计报告，记录指标、剩余问题分类、接受/不接受边界。
- 在 V1 中增强暗色/复杂卡片按钮的 OCR-anchored control surface 召回。
- 保持 OCR 为唯一文字权威，按钮文字仍输出为 OCR TextLayer。
- 对被 accepted control surface 拥有的按钮背景禁止 raster crop / text inpaint。
- 跑单测、Python compile、86 图 batch，并人工复核剩余高风险局部 contact sheet。

不包含：

- 不继续 V2/V3。
- 不接 YOLO、VLM、OmniParser、M29 或 Go backend。
- 不修改 HTTP API、DSL 合同或输出文件名。
- 不把商品图、地图、封面、头像、图标角标内部文字强行变成普通 TextLayer。
- 不用样本名、路径、文案、品牌、固定坐标、固定 bbox、固定屏幕尺寸写规则。
- 不追求 `rawTextOverlapRaster = 0`。

## Source Evidence

当前 baseline commit：

```text
88a870e fix: repair psd-like v1 media text ownership
```

当前 batch：

```text
/Users/luhui/Downloads/psd_like_v1_media_text_layout_fit_eval_v2
```

局部审计 contact sheet：

```text
/Users/luhui/Downloads/psd_like_v1_media_text_layout_fit_eval_v2/remaining_issue_contact_sheet.png
```

观察结论：

```text
不应修：图标角标数字、电量/日期/星标、商品图/菜品图标签、地图路名、头像角标、封面内部文字。
应修：黑色/深色促销卡片、复杂背景卡片里的有限按钮 surface，例如“立即购买”这类稳定色块按钮。
```

## Implementation

增强现有 `psd_like_layer_decomposition_experiment.py` 的 V1 control surface 检测，而不是新开 pipeline。

通用接受条件：

```text
OCR bbox 被候选 surface 稳定包含
候选是有限按钮/标签/输入框尺度，不是整页、大卡片、大图或 hero
候选非文字区域 fill 稳定、低纹理
文字与候选 fill 有足够亮度/颜色对比
允许外环/边界证据在暗色复杂卡片里更弱，但必须有局部 shape 证据
候选不能主要覆盖高纹理照片、商品图、地图或封面
```

输出不变：

```text
layer_stack.v1.json
draft_runtime.dsl.v1_0.json
preview.html
draft_preview.png
ownership_report.v1.json
diagnostics.md
```

## Acceptance

硬门：

```text
86/86 batch 不崩
DSL valid = 86/86
missingAssetCount = 0
fullPageVisibleRaster = 0
shapeAssetCount = 0
visible text overlap = 0
```

质量门：

```text
暗色/复杂卡片按钮的 controlSurfaceShapeLayerCount 或 controlOwnedRasterSuppressedCount 有合理提升
黑色/深色按钮上的文字不再依赖 raster inpaint 才可见
rasterTextKnockoutCount 不上升
rawTextOverlapRaster 不因误杀 media text 而虚假下降
avg visualMae 不系统性变差
商品图、地图、头像、图标角标内部文字不被误拆
```

停止条件：

```text
如果修复需要按文案、样本、坐标或品牌分支，停止。
如果误把照片/商品图/地图变成 control surface，回滚该规则。
如果全量视觉指标系统性变差，停止并保留审计报告，不替换 baseline。
```

## Validation

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/backend-python
uv run pytest -q tests/test_psd_like_experiment.py
uv run pytest -q
python -m py_compile tools/psd_like_layer_decomposition_experiment.py tools/psd_like_batch_eval.py app/*.py
uv run python tools/psd_like_batch_eval.py \
  --input-dir /Users/luhui/Downloads/测试 \
  --out /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test
git diff --check
git status --short --branch
```

Validation result:

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

Batch output:

```text
/Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval
```

Audit report:

```text
docs/reports/psd-like-v1-baseline-audit-2026-06-02.md
```

## Notes

本阶段接受 Codia 也不是 100% 完美这一事实。目标是可编辑草稿足够好、风险可审计，而不是把截图反推成完美设计源文件。
