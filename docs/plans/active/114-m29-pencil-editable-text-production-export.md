# 114 M29 Pencil Editable Text Production Export

## Summary

把当前验证过的 M29 crop replay 路线固化成一个可追溯工具：读取 M29 physical evidence/replay artifacts，输出 Pencil 可打开的 `.pen` 包。交付拆成三种模式：清理可编辑版、视觉保真版、视觉保真叠 OCR 版。debug 包保留 source/raw/masks/evidence 供排查。

## Scope

- 新增 `services/backend-go/tools/m29_pencil_export.py`。
- 新增 `services/backend-go/tools/m29_pencil_batch_validate.py`。
- 不改 Go Draft runtime、Figma plugin、renderer、psdlike pipeline。
- 不使用文案、case id、固定坐标、固定 bbox、品牌特化规则。

## Contract

清理可编辑输出：

```text
production/design.pen
production/assets/visible/*.png
production/manifest.json
```

视觉保真输出：

```text
visual-fidelity/design.pen
visual-fidelity/assets/visible/*.png
visual-fidelity/manifest.json
```

视觉保真叠 OCR 输出：

```text
visual-ocr/design.pen
visual-ocr/assets/visible/*.png
visual-ocr/manifest.json
```

debug 输出：

```text
debug/design-debug.pen
debug/assets/source.png
debug/assets/raw-crops/*
debug/assets/masks/*
debug/evidence/*
debug/reports/*
```

规则：

```text
clean-editable:
  text_region -> editable text node
  non-text visible region -> image-filled rectangle
  visible crop 与 text mask 重叠 -> 输出 cleaned visible crop
  component crop policy 抑制内部重复碎片

visual-fidelity:
  text_region -> image-filled rectangle
  OCR text 不作为可见 TextLayer
  不做 text knockout
  不做 component 内部碎片抑制

visual-ocr:
  text_region -> image-filled rectangle + visible OCR TextLayer
  OCR TextLayer 使用高对比文字颜色采样，不允许背景色桶赢过文字笔画
  不做 text knockout
  不做 component 内部碎片抑制

所有交付模式:
  raw source/raw crops/masks 不被 .pen 引用
  page frame 必须有自己的 fill，不能透出 Pencil 编辑器主题色
  禁止 full-page visible backing
```

字体策略：

```text
CJK/mixed text: .pen preview uses system-ui, metadata candidates include Noto Sans SC, PingFang SC, Microsoft YaHei, Source Han Sans SC, Arial Unicode MS, Arial.
Latin text: .pen preview uses system-ui, metadata candidates include Inter, SF Pro Text, Segoe UI, Helvetica Neue, Arial.
Text nodes use fixed-width-height, lineHeight 1.0, vertical middle, font size fitted to OCR bbox.
```

## Validation

- Run tool against `/Users/luhui/Downloads/m29_pencil_json_aeterna_cn`.
- Open production `.pen` with Pencil MCP.
- Check layout has no problems.
- Check production `.pen` does not reference `source.png`, `raw-crops`, `masks`, or original text crop paths.
- Check text nodes exist and font fallback metadata exists.

## Current Evidence

Implemented `services/backend-go/tools/m29_pencil_export.py` and validated against the Aeterna M29 replay package:

```bash
python3 -m py_compile services/backend-go/tools/m29_pencil_export.py

python3 services/backend-go/tools/m29_pencil_export.py \
  --input-dir /Users/luhui/Downloads/m29_pencil_json_aeterna_cn \
  --out /Users/luhui/Downloads/m29_pencil_export_aeterna_production \
  --name 'Aeterna CN M29 Production Editable Text' \
  --include-debug-pen
```

Output:

```text
/Users/luhui/Downloads/m29_pencil_export_aeterna_production/production/design.pen
/Users/luhui/Downloads/m29_pencil_export_aeterna_production/production/manifest.json
/Users/luhui/Downloads/m29_pencil_export_aeterna_production/debug/design-debug.pen
```

Observed summary:

```text
textNodes = 25
cropNodes = 199
textKnockoutCropNodes = 21
artTextCropNodes = 2
suppressedDuplicateCropNodes = 9
assetCount = 199
```

Production `.pen` checks:

```text
source.png: false
raw-crops: false
masks/: false
./assets/crops/: false
./assets/masks/: false
text nodes: 25
visible asset refs: 199
```

Pencil MCP validation:

```text
open_document(production/design.pen): success
snapshot_layout(parentId=m29_pencil_page, problemsOnly=true): No layout problems
get_screenshot(parentId=m29_pencil_page): success
```

Additional validation:

```text
art text crop decisions:
  prim_0009 Aeterna -> crop, reason=large_logo_or_display_art_text
  prim_0010 A -> crop, reason=large_single_glyph_art_text

button/card foreground color samples:
  prim_0018 立即点击开始 -> #F8F8F8
  prim_0019 观看官方视频 -> #282838
  prim_0020 下载白皮书 -> #282838
  prim_0022 链抽象跨链 -> #F8F8F8
  prim_0023 RWA资产网络 -> #F8F8F8
  prim_0024 XAgentra -> #F8F8F8
  prim_0026 开放UBI协议 -> #F8F8F8
  prim_0027 收益经济飞轮 -> #F8F8F8
```

Known residual quality issue: the export now suppresses high-overlap duplicate crops, but it still uses a conservative geometry-only gate. Some future samples may need a stricter visible-pixel ownership mask instead of bbox-level crop suppression if overlapping crops are not near-duplicates.

## Three-Mode Evidence

Implemented explicit delivery modes:

```bash
python3 services/backend-go/tools/m29_pencil_export.py \
  --input-dir runs/m29_pencil_batch_20260603_081643_mobile86/cases/0036_case_0036_764d3a58e5/m29 \
  --out /tmp/m29_pencil_modes_test \
  --name 'M29 Modes Test' \
  --mode all
```

Observed mode summaries for `case_0036_764d3a58e5`:

```text
clean-editable:
  textNodes = 99
  cropNodes = 55
  textKnockoutCropNodes = 21
  cropTextNodes = 0
  suppressedInternalCropNodes = 39

visual-fidelity:
  textNodes = 0
  cropNodes = 201
  textKnockoutCropNodes = 0
  cropTextNodes = 99
  suppressedInternalCropNodes = 0

visual-ocr:
  textNodes = 99
  cropNodes = 201
  textKnockoutCropNodes = 0
  cropTextNodes = 99
  suppressedInternalCropNodes = 0
```

Batch smoke:

```bash
python3 services/backend-go/tools/m29_pencil_batch_validate.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --out /tmp/m29_pencil_batch_modes_test \
  --limit 2 \
  --mode all \
  --screenshot
```

Observed:

```text
caseCount = 2
passed = 2
failed = 0
screenshot warnings = 0

artifacts:
  /tmp/m29_pencil_batch_modes_test/contact_sheet.png
  /tmp/m29_pencil_batch_modes_test/contact_sheet.visual-fidelity.png
  /tmp/m29_pencil_batch_modes_test/contact_sheet.visual-ocr.png
```
