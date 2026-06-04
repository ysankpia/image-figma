# 097 PSD-like Layer Decomposition Experiment

- 状态：active
- 创建日期：2026-06-01
- 分支：`feat/omniparser-vlm-pipeline`
- 负责人：Codex

## Goal

验证一条更小的 Draft MVP 路线：

```text
PNG
-> OCR text mask
-> deterministic pixel decomposition
-> PSD-like layer stack
-> inspectable overlays and diagnostics
```

目标不是复刻 Codia，不是恢复原始 Figma tree，也不是继续调 OmniParser/VLM。目标是判断：只靠 OCR 和截图像素的底层规律，能不能稳定切出对编辑有价值的图层。

## First Principles

截图只有像素，没有原始设计树。当前真正需要恢复的不是 UI 组件语义，而是可编辑图层的像素归属：

- OCR 文字是唯一文本权威。
- 高纹理、低文字覆盖区域优先成为 raster layer。
- 低纹理、颜色稳定、矩形感强的区域优先成为 shape layer。
- 不确定区域不强行生成图层，由 reference/diagnostics 暴露。

这条路线更接近 PSD 图层栈：

```text
Reference screenshot
Shape layers
Raster/image layers
OCR text layers
Diagnostics
```

## Scope

包含：

- 新增独立实验工具 `services/backend-python/tools/psd_like_layer_decomposition_experiment.py`。
- 输入为 source PNG 和 OCR artifact。
- 输出 `layer_stack.v1.json`、heatmaps、overlay、reconstructed preview、assets、diagnostics。
- 只使用 Pillow 和 numpy，不调用 provider。
- 跑四张 reference sample 做可视化和计数验证。

不包含：

- 不接入 `/api/draft-preview`。
- 不改 Go backend。
- 不调用 OmniParser。
- 不调用 VLM。
- 不调用 M29。
- 不生成 Figma。
- 不读取 Codia golden JSON 作为 runtime hint。
- 不按样本名、文案、固定坐标、固定 bbox、固定屏幕尺寸写规则。

## Layer Stack Contract

第一版实验输出：

```json
{
  "version": "layer_stack.v1",
  "canvas": {
    "width": 665,
    "height": 1440
  },
  "layers": [
    {
      "id": "raster_0001",
      "type": "raster",
      "bbox": {"x": 48, "y": 612, "width": 120, "height": 160},
      "z": 2000,
      "asset": "assets/raster_0001.png",
      "scores": {
        "texture": 0.82,
        "edge": 0.64,
        "entropy": 0.77,
        "textOverlap": 0.03,
        "shapeLikeness": 0.12
      },
      "reason": "high_texture_low_text_overlap"
    },
    {
      "id": "text_0001",
      "type": "text",
      "bbox": {"x": 199, "y": 442, "width": 147, "height": 32},
      "z": 3000,
      "text": "星甲魂将传",
      "reason": "ocr_authority"
    }
  ],
  "diagnostics": {
    "fullPageVisibleRaster": 0,
    "tinyRasterFragments": 0,
    "textOverlapRaster": 0,
    "layerCount": 2
  }
}
```

## Algorithm V0

V0 先验证 raster + OCR：

1. 读取 PNG 和 OCR blocks。
2. 用 OCR bbox 加 padding 生成 text mask。
3. 将图像切成固定 tile。
4. 对每个 tile 计算颜色方差、边缘密度、局部熵、dominant color ratio、unique color count、text mask coverage。
5. 生成 raster likelihood heatmap。
6. 对 heatmap 做阈值、形态学 close、连通域和 bbox 拟合。
7. 拒绝过小、过大、整页、极端长宽比、文字覆盖太高的候选。
8. 输出 raster layers、OCR text layers、overlay、reconstructed preview。

V1 再验证 shape：

1. 从低纹理、高 dominant color ratio 的区域生成 shape likelihood。
2. 只接收大面积、颜色稳定、矩形感强的候选。
3. shape 不裁 asset，只记录 fill。
4. shape z 低于 raster/text。

## Acceptance

硬门：

- 不调用网络和 provider。
- 不输出 visible full-page raster backing。
- OCR text 不改写。
- raster asset ref 全部存在。
- shape 不写 asset。
- 不因单张图失败导致脚本崩溃。

质量信号：

- 主图片、头像、封面、banner 或复杂 icon 能成为 raster candidate。
- image asset 数量不能爆炸。
- tiny raster fragments 数量低。
- text overlap raster 数量低。
- overlay 能直接看出误切和漏切。

## Current V5 Result

V3 增加了 OCR text ownership 保护：raster asset 可以保留完整视觉区域，但导出 PNG 时会对 OCR text mask 做 alpha knockout，并在 `ownership_report.v1.json` 中记录覆盖了哪些 OCR block。这样普通文字仍由 OCR TextLayer 拥有，raster 不再重复拥有同一片可见文字像素。

V4 在不接入 HTTP API 的前提下，额外输出离线 `draft_runtime.dsl.v1_0.json`、`preview.html`、`preview_report.md` 和 `draft_preview.png`，用于验证 PSD-like layer stack 能被 Draft Runtime 合同消费。

V5 修复了 V4 的主要可用性问题：

- 页面背景不再写死为白色，改为从边缘主色簇估计 `pageBackground`。
- 新增 `background_surface_band` shape，用低纹理、稳定色、横向连通区域恢复大面积底板/卡片 surface。
- 新增 `foreground_object_on_surface` raster，用局部背景主色差异恢复平滑插画/图标，不再只依赖高纹理 heatmap。
- OCR TextLayer 颜色改为从 bbox 内“相对边缘背景对比最大”的颜色簇估计，支持黑字白底和白字彩底。
- 修复 `@image-figma/dsl-schema` 构建配置，使 package entry 与实际 `dist/index.js` 对齐，并让 Node ESM 产物可直接导入。

四图当前结果：

```text
t018   text=47  raster=25  shape=18  surfaceShape=12  visibleTextOverlap=0  rawTextOverlap=2  knockoutRasters=4  missingAsset=0
t022   text=42  raster=15  shape=9   surfaceShape=6   visibleTextOverlap=0  rawTextOverlap=0  knockoutRasters=3  missingAsset=0
lizhi  text=27  raster=26  shape=11  surfaceShape=7   visibleTextOverlap=0  rawTextOverlap=0  knockoutRasters=0  missingAsset=0
xianyu text=39  raster=17  shape=12  surfaceShape=11  visibleTextOverlap=0  rawTextOverlap=0  knockoutRasters=2  missingAsset=0
```

已满足的硬门：

- `visibleTextOverlap = 0`
- `missingAsset = 0`
- `fullPageVisibleRaster = 0`
- `tinyRasterFragments = 0`
- 四图 `draft_runtime.dsl.v1_0.json` 通过正式 `@image-figma/dsl-schema` build 产物的 `validateDraftRuntimeDSL`
- Renderer Draft Runtime 测试通过
- 四图 `preview_report.md` 的 missing image refs 为 `0`
- 四图 `draft_preview.png` 非空且尺寸匹配源图

仍未解决：

- 这仍是 PSD-like 草稿，不是 Codia-like 结构树。它能提供可编辑文字、主要图片、底板 shape 和可替换 raster，但不恢复 Auto Layout、组件、嵌套语义。
- OCR text 的字体、字号、对齐、行高仍粗糙；这是 text style estimation 问题，不是 layer ownership 问题。
- 圆角、阴影、渐变、半透明遮罩没有系统恢复，当前 surface 以纯色 shape 为主。
- 个别小标签/复杂遮罩区域仍可能被平滑 surface 或 raster 简化。

## Validation

命令：

```bash
cd services/backend-python
python -m py_compile tools/psd_like_layer_decomposition_experiment.py
uv run pytest -q
```

四图实验：

```bash
cd services/backend-python
uv run python tools/psd_like_layer_decomposition_experiment.py \
  --image ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
  --ocr /tmp/backend_python_omni_vlm_smoke/t018/evidence/ocr_blocks.v1.json \
  --out /tmp/psd_like_layer_exp/t018
```

同样跑 `t022`、`lizhi`、`xianyu`。如果 OCR artifact 不存在，允许先用 `--ocr optional` 跑无 OCR 降级实验，但不能据此判断文字层质量。

最后检查：

```bash
git diff --check
git status --short --branch
```
