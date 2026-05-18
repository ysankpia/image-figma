# M29 Visual Primitive Graph Harness

- 状态：completed
- 创建日期：2026-05-18
- 负责人：Codex

## Goal

M29 建立独立的 `PNG -> visual primitive graph` 反渲染 harness。它输出 `nodes.json`、局部 image/symbol assets、debug overlays 和 preview sheet，用来验证截图像素能否先被分成 `text`、`shape`、`image`、`symbol`、`unknown` 五类视觉原语。

M29 不继续优化 M28 icon crop，不接 SAM2/OpenCV/OCR provider，不生成 Figma，不修改 DSL，不进入上传主链路，也不替换 M8 `/primitives` 合同。

## Implementation

新增：

```text
backend/app/visual_primitive_graph.py
backend/scripts/run_m29_visual_primitive_graph.py
backend/tests/test_visual_primitive_graph.py
```

M29 使用独立合同 `M29VisualPrimitiveGraphDocument v0.1`，避免和 M8 `VisualPrimitiveDocument` 混淆。所有 bbox 都是原图像素坐标 `[x, y, width, height]`，整数，左闭右开。所有 binary mask 都是 row-major、1 byte per pixel、`0=false`、`255=true`。

M29 复用 `png_tools.py` 的 PNG decode/encode 能力，不搬迁、不重命名底层 PNG 工具。

## Pipeline

```text
PNG decode
-> bbox/mask/metrics helpers
-> text exclusion mask
-> initial components / large regions
-> obvious shape detection
-> conservative image detection
-> image protection mask
-> foreground mask after exclusions
-> remaining connected components
-> symbol detection
-> unknown / blocked classification
-> containment relations
-> asset export
-> debug overlays
-> preview sheet
-> validation
-> nodes.json
```

Shape 分为：

```text
protective_shape: background, card_background, search_field_background, large_container, separator
interactive_shape: button_background, badge_background, small_ellipse, small_rounded_rect, icon_button_background
```

`text_mask` 和 `image_protection_mask` 永远排除；`protective_shape` 可排除；`interactive_shape` 不完全排除，以便后续还能找内部 symbol。

Image detection 必须保守。低置信度 image-like 区域进入 `unknown`，不得进入 protection，避免误吞 UI 容器内的 symbol/shape。

## Run

```bash
cd backend
uv run python scripts/run_m29_visual_primitive_graph.py \
  --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png" \
  --output-dir "storage/m29_visual_primitive_graph"
```

输出目录若已存在且未传 `--overwrite`，脚本自动加时间戳后缀，保留旧证据。

输出：

```text
nodes.json
preview_sheet.png
assets/images/*.png
assets/symbols/*.png
overlays/01_text_exclusion.png
overlays/02_initial_components.png
overlays/03_shapes.png
overlays/04_images.png
overlays/05_image_protection.png
overlays/06_foreground_mask.png
overlays/07_symbols.png
overlays/08_final_nodes.png
```

## Acceptance

合成测试必须严格：

```text
text exclusion 后不生成 symbol
solid rect -> shape，不是 image/symbol
thin line -> line/separator shape，不是 symbol
complex texture patch -> image
low-confidence image -> unknown 且不 protection
image protection 内部碎片 blocked，不进入 symbol
interactive shape 内部 symbol 仍可检测
asset export 只裁 image/symbol
overlay PNG 可读
document validation 拒绝坏 bbox、重复 id、缺失 asset、坏 relation
```

真实图 smoke 是 diagnostic，不以 0 误检为硬门槛。人工验收重点看 `preview_sheet.png` 和 overlays：图片资产是否整块保护、shape 是否从背景/容器中分离、文字是否避免进入 symbol、symbol 是否没有被大 image protection 吞掉。

## Validation

```bash
cd backend && uv run pytest tests/test_visual_primitive_graph.py -q
cd backend && uv run pytest
pnpm run check
git diff --check
```

M29 storage output 是本地证据，不提交 `backend/storage/`。
