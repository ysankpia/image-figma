# M32 Figma Boolean Subtract and Backend RGBA Masking

- 状态：completed
- 创建日期：2026-05-19
- 负责人：Antigravity

## Goal

彻底打破假底图“纯色色块盖字”的枷锁，放弃在后端进行像素背景采样和填充，改为将已成功 Materialize（激活）的可编辑文本/图标 bounding boxes 绝对坐标以 `meta.maskBBoxes` 数组的形式写入 DSL，并由 Figma Renderer 消费，通过调用 Figma 原生 Boolean Subtract (`figma.subtract`) 能力对 fallback image 节点进行镂空裁剪。
同时，后端实现 binary mask 到透明 alpha 通道的转换逻辑（RGBA），保证切出的 icon 和 asset 资产边缘清晰、无毛边。

## Scope

包含：
- 在 `png_tools.py` 中新增 `encode_rgba_png` 以支持 32-bit RGBA 导出。
- 在 `png_tools.py` 中实现 `crop_mask_pixels_to_rgba_png`，将 binary mask 直接转换成输出 PNG 的 alpha 通道。
- 在 `evidence_grounded_dsl_materialization.py` 的 M30 pipeline 中，收集已激活文本节点的绝对 Bounding Box，注入 fallback region 节点的 `meta.maskBBoxes` 属性。
- 扩展 Renderer API `FigmaAdapter` 接口，支持 `createBooleanSubtract`。
- 在 Figma 插件端和 mock adapter 端实现 `createBooleanSubtract` (调用原生 `figma.subtract`)。
- 修改 Renderer 的 `renderImage`，在存在 `meta.maskBBoxes` 时将 fallback node 与生成的 mask nodes 一起组成 Boolean Subtract 组。

不包含：
- 不做 Auto Layout。
- 不引入外部 YOLOv8 依赖（保留到 M33 开展）。
- 不改变已有图层层级（Boolean Subtract 作为独立节点存在）。

## Steps

1. **后端 RGBA 支持**：在 `png_tools.py` 中实现 `encode_rgba_png`，编写对应 unit tests。
2. **后端 Mask 映射**：实现 `crop_mask_pixels_to_rgba_png`，并在 materialization 过程中将 maskBBoxes 写入 DSL 对应 fallback nodes 的 `meta` 中。
3. **Renderer API 扩展**：在 `FigmaAdapter` / `figmaAdapter.ts` / `FakeFigmaAdapter` 中定义并实现 `createBooleanSubtract`。
4. **Renderer Image 镂空**：修改 `renderImage.ts`，如果 image 节点包含 `meta.maskBBoxes` 且存在 parent，则构建 subtraction nodes。
5. **单元测试与集成测试**：在 `renderDesign.test.ts` 中编写测试，确保 mock 节点能正确移除原 baseNode 并以 `BOOLEAN_OPERATION` 节点挂载。

## Acceptance

- `pnpm test` 和 `pytest` 跑通。
- Fallback region 节点的 `meta.maskBBoxes` 包含已激活元素的绝对 BBox。
- Renderer 执行后，假底图转为 `BOOLEAN_OPERATION` 类型，且被 mask 的区域对应的 dummy rectangles 在 group 内，原 fallback node 不会以裸 rectangle 留在父节点中。

## Validation

```bash
pnpm test
pytest backend/tests/test_png_tools.py
pytest backend/tests/test_evidence_grounded_dsl_materialization.py
```
