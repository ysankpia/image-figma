# M34 OCR Artistic and Rotated Text Filtering

- 状态：completed
- 完成日期：2026-05-20
- 负责人：Antigravity

## Goal

通过第一性原理（First-Principles）改进文字与图形的分类解耦。针对轮播图/海报（Carousel Banner）、促销气泡、艺术字等场景中的“斜置文字”或“高背景复杂度艺术字”，建立通用的后台过滤与判定机制（Artistic & Rotated Text Filter）。

防止此类文字被强行识别为标准 UI 文本层导致背景在像素级被擦除（破洞填充）且文字本身被渲染为简陋的系统字体。使其安全地作为底层大图资产的有机组成部分予以完整保留，还原最真实的设计稿视效。

> M34.1 修正：本阶段的 angle/polygon OCR metadata 是正确方向，但“在 M29 前 drop OCR text boxes”是错误抽象。当前事实来源是 [034-1-preserve-graphic-text-evidence-and-editability-decision.md](034-1-preserve-graphic-text-evidence-and-editability-decision.md)：OCR 证据必须保留，M30 再决定 `editable_text` 或 `graphic_text_preserve_in_fallback`。

---

## First Principles & Design Decisions

1. **功能性文本与艺术/装饰性图形的本质区别**：
   - **功能性文本**：处于简易纯色背景上，水平排布（旋转角为 0°），要求高可读性、标准字体。必须 OCR 为 Figma 文本层。
   - **艺术字/装饰性文本**：常处于高色数、强渐变的海报或轮播图内，带有特定偏转角。其艺术视觉表达（如渐变、阴影、特定艺术字体）在转换为 Figma 文本时会完全丢失。其本质是底层“图形资产”的一部分，不应当被擦除和文本化。
2. **判定指标设计（通用且非特化）**：
   - **偏转角度（Rotation Angle）**：基于 Baidu PP-OCRv5 返回的 `rec_polys` 多边形顶点坐标，计算 4 个线段角度模 90 度的偏移量（对齐到最近的水平/垂直网格的最小倾角）。M34.1 后，该指标用于 M30 `graphic_text_preserve_in_fallback` 决策，不再用于删除 OCR evidence。
   - **背景复杂度（Background Complexity）**：采样文字区域像素，测量颜色数（Color Count）与纹理得分（Texture Score）。M34.1 后，高复杂度背景上的文字会保留在 fallback，并在 M30 report 中解释原因。
3. **M34.1 后的阶段修正**：
   - OCR 结果解析阶段只负责保留 `angle` / `polygon` 等证据。
   - 不再在 M29 前丢弃图形化文字。
   - 是否生成 Figma text layer 由 M30 text editability decision 决定。

---

## Scope

### 包含：

1. **设置与阈值配置**：
   - 在 `backend/app/config.py` 中新增阈值配置。M34.1 后的 active 开关是 `OCR_TEXT_EDITABILITY_ENABLED` 和 `OCR_GRAPHIC_TEXT_PRESERVE_ENABLED`；`OCR_ARTISTIC_TEXT_FILTER_ENABLED` 只作为 legacy alias，不再对应 Settings 字段。
   - `ocr_max_rotation_angle`: 最大允许偏转角度（度），默认 `3.0`。
   - `ocr_max_background_texture`: 文字框最大背景纹理阈值，默认 `0.45`。
   - `ocr_max_background_color_count`: 文字框最大背景颜色数，默认 `32`。
2. **多边形偏转角度计算**：
   - 在 `backend/app/ocr_baidu.py` 中，遍历 `rec_polys` 的顶点，计算 4 个线段角度模 90 度的偏移量（对齐到最近的水平/垂直网格的最小倾角）。
   - 在 `OCRBlock` 级别增加 `meta` 字典字段，传递 `angle` 及 `polygon`。
3. **像素级背景复杂度校验**：
   - M34 最初计划在 `backend/app/m30_upload_pipeline.py` 中转换为 `M29TextBox` 前进行过滤降级。
   - M34.1 已废弃该 drop 流程；当前实现改为在 M30 materialization 前做 text editability decision。
4. **单元测试验证**：
   - 编写针对多边形角度计算函数的 Pytest。
   - M34.1 后，验证斜置艺术字 evidence 仍保留，M30 不生成普通 text layer，并在 report 中标记 preserve。

### 不包含：

- 对 Figma 中已倾斜文本对象的旋转属性自动回写（由于 Figma API 对斜体/旋转文字还原较为复杂且字体包受限，本次工作只聚焦于将其**保留在背景大图**中，不将其转成文本层）。

---

## Steps

### 1. 配置项定义
- 修改 [config.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/config.py)：
  - M34 原本添加过滤开关和阈值；M34.1 后 active 配置为 `ocr_text_editability_enabled`、`ocr_graphic_text_preserve_enabled`、`ocr_max_rotation_angle`、`ocr_max_background_texture`、`ocr_max_background_color_count`。

### 2. 实体元数据扩展与旋转角计算
- 修改 [ocr.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/ocr.py)：
  - 给 `OCRBlock` 添加 `meta: dict[str, Any] = field(default_factory=dict)` 属性。
- 修改 [visual_primitive_graph.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/visual_primitive_graph.py)：
  - 给 `M29TextBox` 添加 `meta: dict[str, Any] = field(default_factory=dict)` 属性。
- 修改 [ocr_baidu.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/ocr_baidu.py)：
  - 实现 `estimate_polygon_rotation(poly: list[list[float]]) -> float` 函数，通过 4 个顶点模 90 度转换计算平均绝对偏转角。
  - 在 `parse_ocr_result` 时计算 angle，将其存入 `OCRBlock.meta["angle"]` 和 `OCRBlock.meta["polygon"]` 中。

### 3. 主流程通用过滤器实现
- 修改 [m30_upload_pipeline.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m30_upload_pipeline.py) 和 [text_masked_media_audit.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/text_masked_media_audit.py)：
  - M34.1 后，`text_boxes_from_ocr_document` 只转换和保留 OCR evidence，不执行 artistic text drop。
  - `angle >= ocr_max_rotation_angle` 或背景复杂度超标的文字由 M30 标记为 `graphic_text_preserve_in_fallback`，而不是从证据链删除。

### 4. 编写回归与单元测试
- 修改/新建后端测试 [test_baidu_ocr.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/tests/test_baidu_ocr.py)：
  - 编写旋转角计算的准确性验证。
  - M34.1 后的回归应断言带偏转角的 OCR 输入仍保留 `meta.angle` / `meta.polygon`，但不会生成 `m30_text_member`。

---

## Acceptance

1. **斜置字自动保留在背景中**：
   - 上传带斜置促销字/艺术字的 PNG。
   - M34.1 后，该倾斜文字**不被挖空/不被擦除**，背景依然平整，Figma 中该位置**无任何文本节点**，同时 M30 report 可以解释它被 `graphic_text_preserve_in_fallback` 保留。
2. **普通水平文字正常物化**：
   - 水平的正常 UI 文字（如标题、说明文案）依然能 100% 正常进行 OCR、背景像素填充擦除，以及 Figma 文本层生成。
3. **后端测试通过**：
   - 所有的 `pytest` 运行通过，无警告、无错误。

---

## Validation

- M34.1 回归测试：`cd backend && uv run pytest tests/test_baidu_ocr.py tests/test_evidence_grounded_dsl_materialization.py tests/test_m30_upload_pipeline.py -q`。
- 检查代码风格：`git diff --check`
