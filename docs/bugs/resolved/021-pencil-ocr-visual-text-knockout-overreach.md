# Bug: Pencil OCR visual text knockout overreach

- 状态：resolved
- 创建日期：2026-06-04
- 影响范围：`services/pencil-python-backend` 的 `clean-editable` 和 `visual-ocr` 模式

## Summary

部分商品图、海报、促销价、包装字和局部视觉块内部文字被 OCR 识别后，Pencil exporter 默认把它们全部提升为可见 `TextLayer`，并用这些 OCR bbox/mask 去清理底层 bitmap crop。结果是原本视觉上应属于 raster 的文字被擦掉，替换后的系统字体 TextLayer 又不能复刻原图排版，出现缺字、淡字、重影或视觉割裂。

## Reproduction

使用真实 PSD-like evidence 导出：

```text
/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/work/page_0007/psdlike_pencil_evidence
```

修复前 `page_0007`：

```text
clean-editable textNodes=21
visual-ocr     textNodes=21
```

所有 OCR 文本都记录为：

```json
{"decision":"editable_text","reason":"normal_ocr_text"}
```

典型受影响文本包括促销价格、折扣、局部赠品标签和商品视觉块内部文字。

## Root Cause

OCR 是文字事实来源，但 OCR 不应该直接决定可见像素所有权。原逻辑只有很窄的 `art_text_rejection_reason()`，除此之外只要 `mode.visible_ocr_text=True` 就：

```text
text_region -> editable_text_layers
text_region -> editable_text_primitives
editable_text_primitives -> text knockout mask
```

这把“普通 UI 文本”和“媒体/海报/商品/促销视觉文字”混为一类。前者可以由 TextLayer 拥有像素；后者应该继续由 raster 拥有，不能参与 knockout。

## Fix

在 `app/exporter/single_page.py` 增加 `visual_text_rejection_decision()`：

- 如果 OCR text 被局部 `image_region` / `unknown_region` / `symbol_region` / `art_text_region` raster owner 高覆盖，且 owner 不是整页、大背景或普通低纹理 control surface，则该文字保留为 `visual_text_region` raster crop。
- 显示型价格、折扣、满减、到手价等促销文字保留为 raster。
- 价格、折扣、满减、领取等邻近 OCR block 先组成 `visual_text_cluster.v1`，整组统一保留为 raster，避免 `"9"` 和 `"折"` 这类同一视觉对象被拆成一半 TextLayer、一半 bitmap。
- `visual_text_region` 不加入 `editable_text_primitives`，所以不会擦底图。
- `visual_text_region` / `art_text_region` / `text_region` 自身也不再执行 knockout，避免保留文字 crop 被清成 `.clean.png`。
- manifest 增加 `visualTextCropNodes`，项目级 report 也展示该计数。

该规则只依赖 bbox、role、局部 owner、复杂度 measurements、画布尺度和文本字符类别；不依赖文件名、品牌、页面序号、固定坐标或固定文案。

## Regression Guard

新增测试 `test_visual_text_inside_local_raster_stays_raster_owned`：

- 构造一个局部高纹理 `image_region`，内部包含价格 OCR。
- 构造被 OCR 拆开的 `"9"` / `"折"` / `"满298使用"` 促销文字簇。
- `clean-editable` 和 `visual-ocr` 必须把该 OCR 记录为 `text_inside_raster_owner`。
- 被拆开的促销文字必须进入同一个 `visual_text_cluster.v1`。
- 不生成对应 TextLayer。
- 不产生 text knockout。
- `.pen` 中不出现该价格作为 text node content。

现有项目级测试继续断言普通 UI OCR 文本仍生成 TextLayer，防止规则吞掉低纹理 UI 文本。

## Validation Evidence

- `cd services/pencil-python-backend && uv run python -m py_compile $(find app tests -name '*.py' | sort)`
- `cd services/pencil-python-backend && uv run pytest -q`
- Targeted real export:
  `/Volumes/WorkDrive/pencil-exports/visual-text-cluster-page0007-20260604`
- 修复后 `page_0007`：

```text
clean-editable textNodes=8 visualTextCropNodes=13 textKnockoutCropNodes=0
visual-ocr     textNodes=8 visualTextCropNodes=13 textKnockoutCropNodes=0
visual-fidelity textNodes=0 cropTextNodes=21 textKnockoutCropNodes=0
```

- Pencil CLI preview:
  - `/Volumes/WorkDrive/pencil-exports/visual-text-cluster-page0007-20260604/preview/clean-editable.png`
  - `/Volumes/WorkDrive/pencil-exports/visual-text-cluster-page0007-20260604/preview/visual-ocr.png`

## Prevention Notes

不要把 `rawTextOverlapRaster = 0` 当成目标。截图反推设计稿时，商品图、海报、地图、封面、包装、图标角标和促销价格内部文字经常应该继续属于 raster。只有普通 UI 文本才应该拥有可见文字像素并授权 knockout。
