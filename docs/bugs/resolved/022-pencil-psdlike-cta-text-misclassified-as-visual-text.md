# Bug: Pencil PSD-like CTA text misclassified as visual text

- 状态：resolved
- 创建日期：2026-06-04
- 影响范围：`services/pencil-python-backend` 的 PSD-like boundary source，`clean-editable` 和 `visual-ocr` 模式

## Summary

PSD-like layer stack 中普通低纹理 CTA/Button 文字已经由 OCR 正确识别，但 Pencil exporter 把承载该文字的蓝色按钮 raster 误判为 `visual_text_region` owner。结果该文字不生成可编辑 TextLayer，只作为文字 crop 参与输出；后续 crop dedupe/覆盖关系可能让按钮文字在 `.pen` 中变弱或消失。

## Reproduction

真实样本：

```text
/Users/luhui/Downloads/兼职
```

对应产物：

```text
/Volumes/WorkDrive/pencil-exports/pencil-jianzhi-psdlike-reuse-20260604/work/page_0005/psdlike_pencil_evidence/m29_physical_evidence.v1.json
```

证据：

```json
{
  "id": "psd_text_0051",
  "primitiveType": "text_region",
  "text": "查看提交记录",
  "bbox": {"x": 581, "y": 1442, "width": 182, "height": 35}
}
```

修复前 `production/manifest.json` 和 `visual-ocr/manifest.json` 里该文字被判为：

```json
{
  "primitiveId": "psd_text_0051",
  "decision": "crop",
  "reason": "text_inside_raster_owner",
  "ownerPrimitiveId": "psd_raster_0022"
}
```

最终项目级 `.pen` 中搜索不到 `查看提交记录`，说明该普通 CTA 文本没有进入可编辑 TextLayer。

## Root Cause

`visual_text_rejection_decision()` 用来保护商品图、海报、促销价和复杂图片块内部文字，不让它们被 OCR TextLayer 接管。但 `looks_like_simple_control_owner()` 的低纹理控件高度保护阈值固定为 `84px`。

真实移动截图中该 CTA owner bbox 为：

```text
width=424 height=88 aspect=4.82 areaRatio=0.0238 complexity=0.3334
```

它只比固定阈值高 4px，于是没有被识别为普通简单控件，继续被当成 `image_region` 视觉文字 owner，导致 OCR 文字被降级成 crop。

## Fix

将简单控件高度上限改成随画布短边轻微自适应：

```text
control_height_limit = clamp(short_side * 0.12, 84, 112)
```

仍然保留面积、aspect、complexity 和 text ratio gate。这个规则只依赖画布尺度、bbox、复杂度和覆盖关系，不依赖页面位置、文案、文件名、品牌或固定坐标。

## Regression Guard

新增 `test_low_texture_cta_text_stays_editable`：

- 构造 941x1672 移动截图比例下的 424x88 低纹理蓝色 CTA；
- CTA 内部 OCR 文本 `查看提交记录` 必须在 `production` 和 `visual-ocr` 中保持 `editable_text`；
- `.pen` 中必须包含该文字；
- 原有 `test_visual_text_inside_local_raster_stays_raster_owned` 继续保证商品/促销视觉文字仍保持 raster owned。

## Validation Evidence

Targeted regression:

```bash
cd services/pencil-python-backend
uv run pytest -q \
  tests/test_project_builder.py::test_low_texture_cta_text_stays_editable \
  tests/test_project_builder.py::test_visual_text_inside_local_raster_stays_raster_owned
```

结果：

```text
2 passed
```

Static and full backend tests:

```bash
cd services/pencil-python-backend
uv run python -m py_compile $(find app tests -name '*.py' | sort)
uv run pytest -q
```

结果：

```text
11 passed, 1 warning
```

真实样本重新导出：

```bash
cd services/pencil-python-backend
uv run python -m app.cli.export_project \
  --manifest /Volumes/WorkDrive/pencil-exports/psdlike-jianzhi-realocr-20260604/input_manifest.v1.json \
  --out /Volumes/WorkDrive/pencil-exports/pencil-jianzhi-psdlike-reuse-cta-fix-20260604 \
  --project-name "Jianzhi PSD-like Reuse CTA Fix" \
  --mode all \
  --columns auto \
  --boundary-source psdlike \
  --psdlike-artifacts-root /Volumes/WorkDrive/pencil-exports/psdlike-jianzhi-realocr-20260604 \
  --include-debug
```

第 5 页 `production` / `visual-ocr` 的 `psd_text_0051` 修复后：

```json
{
  "primitiveId": "psd_text_0051",
  "text": "查看提交记录",
  "decision": "editable_text",
  "reason": "normal_ocr_text"
}
```

项目级 `.pen` 检查：

```text
clean-editable contains 查看提交记录 = True
visual-ocr contains 查看提交记录 = True
visual-fidelity contains 查看提交记录 = False
```

`visual-fidelity` 仍保持 crop-only，这是该 mode 的预期语义。

Pencil CLI preview:

```text
/Volumes/WorkDrive/pencil-exports/pencil-jianzhi-psdlike-reuse-cta-fix-20260604/preview/clean-editable.png
/Volumes/WorkDrive/pencil-exports/pencil-jianzhi-psdlike-reuse-cta-fix-20260604/preview/root-cause-crops/cta-before-after.png
```

## Prevention Notes

不要把所有包含 OCR 文本的 `image_region` 都当成媒体 owner。低纹理、横向、局部、按钮比例的 owner 更可能是普通 UI control surface；它内部的短标签应优先进入 editable TextLayer。视觉文字保护规则必须继续只保护复杂媒体、商品图、海报和促销显示文字。
