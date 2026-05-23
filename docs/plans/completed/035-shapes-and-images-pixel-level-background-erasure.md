# M35 Shapes and Images Pixel-Level Background Erasure

- 状态：completed
- 负责人：Antigravity

## Goal

通过第一性原理（First-Principles）改进 Shape（形状/色块）与 Image/Icon（图片/图标）与背景图层的解耦方式。继承 M33 的文字像素级擦除机制，在后端像素层面将已物化为独立图层的 Shape 和 Image/Icon 从背景 fallback 图中擦除并填充，彻底消除设计稿中的“重影（double rendering / ghosting）”现象。

---

## First Principles & Alignment

1. **图层解耦的完整性**：在 UI 设计稿中，任何被提升为独立可编辑层（如独立的矩形按钮、背景卡片、图标或插图）的元素，都不应当继续保留在背景图中。
2. **重影现象的根源**：目前 M30 只擦除了 Text。已物化为单独 `rect` 的 Shape 候选、以及物化为单独 `image` 的图片/图标，其像素依然残留在背景大图上。当用户在 Figma 中移动或删除这些图层时，底下会露出完全一模一样的“重影”，破坏了设计稿的可编辑性与质量。
3. **像素擦除的普适性**：
   - 对于物化 Shape：将其 bbox 区域在背景图中以其周围的 dominant 容器背景色填充。
   - 对于物化 Image/Icon：将其 bbox 区域在背景图中以其周围的 dominant 容器背景色填充。
   - 这样在 Figma 中拖走 Shape 或 Image 之后，底层依旧是一张干净平整的父容器背景。

---

## Scope

### 包含：

1. **配置开关扩展**：
   - 在 `M30Options` 和后端 `Settings` 中新增 `shape_erasure_enabled` (默认 `True`) 与 `image_erasure_enabled` (默认 `True`)。
2. **后端像素级擦除实现**：
   - 在 `evidence_grounded_dsl_materialization.py` 中，编写 `erase_shapes_from_fallback_images` 和 `erase_images_from_fallback_images` 模块。
   - 获取所有已成功物化的 `shape` 节点（以 `m30_shape_candidate` role 存在）与 `image` 节点（以 `m30_visual_asset` role 存在）。
   - 对它们对应的绝对/相对坐标进行边界约束校验。
   - 利用 `sample_rect_edges_dominant_background` 采样这些节点 bbox 外侧的 dominant 背景色，在背景 fallback 像素行直接覆写该颜色。
3. **单元测试与回归测试**：
   - 在 `test_evidence_grounded_dsl_materialization.py` 中补充测试，验证 Shape 与 Image 的背景擦除填充行为。

### 不包含：

- **透明 Icon 自动遮罩切片（Transparent Slicing）**：这属于 M36 阶段的独立任务，本阶段仅聚焦于将已有 Image/Icon 的 bbox 区域从 fallback 大图中擦除，使用纯色填充背景。
- 对超大复杂背景（如插画、照片）的纹理重建。

---

## Steps

### 1. 扩展 M30Options 与系统配置
- 在 `backend/app/evidence_grounded_dsl_materialization.py` 的 `M30Options` 中添加：
  - `shape_erasure_enabled: bool = True`
  - `image_erasure_enabled: bool = True`
- 在 `backend/app/config.py` 的 `Settings` 中添加相应的环境变量加载支持：
  - `M30_SHAPE_ERASURE_ENABLED` (默认 `true`)
  - `M30_IMAGE_ERASURE_ENABLED` (默认 `true`)
- 在 `backend/app/m30_upload_pipeline.py` 中将 options 传入。

### 2. 实现后端 Shape & Image 擦除
- 在 `backend/app/evidence_grounded_dsl_materialization.py` 中：
  - 在大图 `fallback` 生成与保存前，读取并保存其 `pixels`。
  - 若 `options.shape_erasure_enabled` 为真，则获取所有物化为 `shape` 的节点并擦除。
  - 若 `options.image_erasure_enabled` 为真，则获取所有物化为 `image` 的节点并擦除。
  - 处理可能跨越边界的 bbox，并做安全降级。

### 3. 单元测试覆盖
- 在 `backend/tests/test_evidence_grounded_dsl_materialization.py` 中新增 `test_shape_and_image_erasure_from_fallback_images`，构建带 Shape 和 Image 的虚拟 `m2905` 节点，断言生成的 fallback 图像在特定区域确实被填充擦除。

---

## Acceptance

1. **Shape 擦除**：生成的 fallback 背景图中，物化 Shape 所处的 bbox 像素已被替换为容器背景主色。
2. **Image/Icon 擦除**：生成的 fallback 背景图中，物化 Image/Icon 所处的 bbox 像素已被替换为容器背景主色。
3. **测试通过**：后端 Pytest 100% Passed。
