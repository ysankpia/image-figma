# M33 Pixel-Level Background Text Erasure

- 状态：active
- 创建日期：2026-05-20
- 负责人：Antigravity

## Goal

通过第一性原理（First-Principles）改进文字与背景图层的解耦方式。将原本在 Figma 端执行的“布尔减算矢量蒙版（Boolean Subtract）”遮罩方案，重构为在后端像素层面执行的“像素级背景文字擦除与填充（Pixel-Level Background Text Erasure & Restoration）”。

解决用户拖拽 Figma 文字层时，底层背景图层出现“透明破洞（cutout holes）”和布尔运算图层层级过于复杂的问题，实现接近 Codia 的无缝图层拖动与背景完整性体验。

---

## First Principles & Codia Alignment

1. **图层的本质定义**：UI 设计稿中的背景层与文字层在逻辑上是完全独立且不相交的（文字覆盖在完整的背景之上）。
2. **当前 Boolean Subtract 方案的缺陷**：
   - 它是 Figma 矢量层面的“视效挖空”，并没有修复背景图层本身的像素。
   - 当用户在 Figma 中移动文字层时，底层的布尔减算组会留下一块清晰的“透明破洞”，且层级复杂（包含大量的 dummy mask nodes）。
3. **Codia / 优秀竞品的像素级解耦方案**：
   - 在导出背景大图时，先在**像素域**擦除所有的文字像素，并用合理的邻域背景色/纹理填平（Image Inpainting / Color Filling）。
   - Figma 中的背景图是一张**完好的、没有文字的平整大图**。文字作为独立的矢量文本层盖在上面。
   - 用户可以随意拖走文字、编辑文字，底下的背景图依然完好无损，且没有复杂的布尔减算结构。

---

## Scope

### 包含：

1. **后端像素填充擦除**：
   - 在 [evidence_grounded_dsl_materialization.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/evidence_grounded_dsl_materialization.py) 的 `build_bootstrap_dsl` / `bootstrap_dsl_from_m29` 阶段，对复制到 `assets/m30_fallback/` 的原始 PNG 进行像素处理。
   - 对每个已成功物化的文本节点，利用 `sample_rect_edges_dominant_background` 采样文字边界的背景主色。
   - 在生成的 `fallback` 大图上，直接用该背景色在像素层进行矩形填充（Overwriting text pixels with solid background color）。
2. **Renderer 布尔减算下线**：
   - 在 [renderImage.ts](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/packages/image-to-figma-renderer/src/renderImage.ts) 中下线 Boolean Subtract 的相关渲染逻辑，恢复为平整的 Flat Image 渲染。
   - 从 DSL `meta` 中移除 `maskBBoxes` 的生成与注入逻辑。
3. **单元测试与回归测试**：
   - 新增 Pytest 单元测试，验证后端大图文字像素填充擦除的准确性与边界防溢出。
   - 修正 Vitest 单元测试，移去对 `createBooleanSubtract` 的断言，确保 Renderer 平整渲染的正确性。

### 不包含：

- 复杂的深度学习 / GPU 图像修复模型（Inpainting Models，如 LaMa/Stable Diffusion），坚持轻量级无依赖的图像学填充。
- 对复杂材质（如强光效、精细渐变、复杂噪点插画）的完美纹理融合。一期以局部邻域纯色填充（Solid Color Inpaint）为主。

---

## Steps

### 1. 后端像素填充擦除实现
- 修改 [evidence_grounded_dsl_materialization.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/evidence_grounded_dsl_materialization.py)：
  - 在生成 `m30_fallback` 图片时，先读取原图像素。
  - 遍历所有 `materialized_text`，调用背景色采样函数。
  - 对满足采样置信度的区域，在内存像素行直接覆写为背景色。
  - 将处理后的像素流写回并保存为 `fallback_path` PNG。
- 移去 `inject_mask_bboxes_to_fallback_regions` 注入。

### 2. Figma Renderer 还原与清理
- 修改 [renderImage.ts](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/packages/image-to-figma-renderer/src/renderImage.ts)：
  - 移除 `createBooleanSubtract` 逻辑，完全下线 mask 相关的图层操作。
- 修改 [fakeAdapter.ts](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/packages/image-to-figma-renderer/tests/fakeAdapter.ts) 和 [types.ts](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/packages/image-to-figma-renderer/src/types.ts)，移除不再使用的 Boolean Subtract 适配器方法。

### 3. 验证与单元测试更新
- 编写 [test_evidence_grounded_dsl_materialization.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/tests/test_evidence_grounded_dsl_materialization.py) 测试覆盖，确保填充逻辑在有异常坐标时可以安全降级且不崩溃。
- 更新 [renderDesign.test.ts](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/packages/image-to-figma-renderer/tests/renderDesign.test.ts)，移除布尔减算测试，添加多层级普通 Image 渲染测试。

---

## Acceptance

1. **拖拽无破洞**：在 Figma 中，把文本节点从 `fallback_region` 上拖走时，文本下方原有的背景图层为完好的实体色块，不再呈现布尔镂空的透明洞。
2. **图层零复杂性**：渲染输出的 `fallback_region` 为普通的 Flat `Image` 图层，无 Boolean Subtract 等多级嵌套子矢量矩形，图层层级干净清爽。
3. **全部测试通过**：所有的 Pytest 和 Vitest 测试用例 `100% Passed`。

---

## Validation

- 运行后端测试：`cd backend && uv run pytest`
- 运行前端测试：`pnpm test`
- 运行代码检查：`git diff --check`
