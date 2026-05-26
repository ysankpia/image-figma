# 02 M29.0 Raw Primitive Graph Audit

## 1. source truth
本层认定的物理事实为 **“像素级连通域、二值掩膜（Binary Mask）、OCR 文本框与底层几何形状的粗分类与特征度量”**。它在无语义假设的前提下提取图像中的连通色块、高频边缘、纹理指标（textureScore）与色彩多样性（colorCount）。

## 2. input artifacts
* 源图字节流：`storage/uploads/{taskId}.png`
* 原始 OCR 结构：从外部/Mock OCR Ingestion 拿到的 `M29TextBox` 列表。

## 3. output artifacts
* 物理基元文档：`storage/upload_previews/{taskId}/m29/nodes.json`（定义了 raw nodes、relations 与 blocked primitives）。
* 诊断用叠加图：`storage/upload_previews/{taskId}/m29/overlay_nodes.png` 等。

## 4. code entrypoints
* 协调管理器入口：[backend/app/visual_primitive_graph.py#L113](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/visual_primitive_graph.py#L113)
* 二值掩膜生成：[backend/app/visual_primitive/components.py#L46](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/visual_primitive/components.py#L46)
* 形状/图像/符号分类器：[backend/app/visual_primitive/detectors.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/visual_primitive/detectors.py)
* 支撑背景爬网：[backend/app/visual_primitive/support.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/visual_primitive/support.py)

## 5. decision authority
* **拥有判定权**：拥有将连通域初步分配为 `"text"`、`"shape"`、`"image"`、`"symbol"`、`"unknown"` 的类型判定权。
* **无权判定**：禁止直接决定元素的最终 Figma 图层层级关系；禁止生成 Figma 组、组件、变量；禁止直接授权背景 Cleanup。

## 6. report-only surfaces
* 本阶段为管线的最底层，其产生的 `nodes.json` 属于物理层事实输出，不是 report-only。但其导出的 `debug_overlays` 和 `preview_sheet.png` 属于纯辅助诊断面。

## 7. allowed facts
* 连通域包围盒（bbox）、面积（area）、质心（centroid）、填充率（fillRatio）。
* 区域色彩复杂度指标：`colorCount`（RGB 通道分箱降采样统计）。
* 局部高频纹理指标：`textureScore`（利用相邻像素色差变异度计算）。
* 局部边缘算子指标：`edgeScore`（边界色差跳变占比）。
* 拟合几何圆角及类型：`geometry` 字段。

## 8. forbidden facts
* 禁止对重合的前前景元素进行“重放”或“舍弃”的生命周期裁决（这是 M29.5 的权限）。
* 禁止分配 `pixelOwner` 的具体物化动作。

## 9. main formulas / gates
* **前背景像素判别门**：
  在估算全局背景 `background` 之后，将与背景欧氏色差大于 42 且非纯白的像素识别为前景：

  $$\text{Foreground}(p) = (\| p - \text{background} \|_1 > 42) \land \neg \text{near\_white}(p)$$

* **Image 置信度评分模型 (`score_image_candidate`)**：
  若面积小于 1200px²，或与 text_mask 冲突度过高，置信度直接清零；否则进行线性累加打分：

  $$\text{Score} = 0.45 + 0.18 \times [\text{color} \ge \text{threshold}] + 0.20 \times [\text{texture} \ge \text{threshold}] + 0.08 \times [\text{fill} \ge 0.70] + 0.07 \times [\text{edge} \ge 0.08]$$

## 10. thresholds and heuristic rationale
* `text_padding = 3`：为 OCR 文字盒扩张 3 像素以保护中文字符边缘的笔画不被当成小 symbol 碎片。
* `ellipse area < 3200` 分界限：经验设计认为 3200 像素以下多为 UI 徽标小圆点（Badge），以上为大卡片/圆角普通椭圆。这容易导致在超高分辨率或大 Badge 下失效，属于**隐性特化**。
* `color_distance > 80`：用于提取 shape 内部的局部高对比前景元素。

## 11. known information loss
* 面积小于 12px 且非 OCR 文本覆盖的微小连通域会被 `connected_components` 直接舍弃（降噪），导致极小的 UI 装饰性点（如密码输入星号）丢失。
* 纯 Python 列表 BFS 栈遍历导致所有连通域的几何拓扑细节被合并为矩形 BBox 结构，丢弃了真实的像素级多边形边缘轮廓。

## 12. known failure symptoms
* 超高分辨率大 Mockup 的全图 connected components 运算导致上传任务在 m29 阶段耗时高达 1.5 秒以上，甚至出现慢速超时。
* 底部的圆点 Indicator（如轮播图下方小分页圆点）如果因为像素连通度低、面积小于 12px，会被在此阶段直接抹去。

## 13. tests / guards
* `tests/test_visual_primitive_graph.py` 覆盖了 text 排除掩膜、connected components 连通域逻辑与 node 输出验证。

## 14. artifact evidence
* 审计发现，任务在 `m29` stage 完成后，产生的 `nodes.json` 包含了各个 Primitive 节点的特征测量：
  ```json
  {
    "id": "shape_001",
    "type": "shape",
    "subtype": "container_background",
    "bbox": [16, 120, 343, 80],
    "metrics": {
      "colorCount": 2,
      "textureScore": 0.004,
      "edgeScore": 0.12,
      "fillRatio": 1.0
    }
  }
  ```

## 15. findings
* **P1 source-chain correctness defect** (`raw_m29`)：手写 Python BFS 存在双重像素循环瓶颈，计算效率在超大 mock 图像下急剧退化。
* **P3 cleanup / dead-path debt** (`raw_m29`)：`detectors.py` 内部硬编码 `area < 3200` 直接判定 shape 为 `badge_background` 还是 `small_ellipse`，忽略了屏幕分辨率（scale）的弹性，形成了隐性特化。

## 16. recommended next action
* **Stage 1 重构**：使用 NumPy 将 foreground 二值矩阵向量化，引入 scikit-image `skimage.measure.label` 重写 `connected_components`，用 C 级效率彻底取代纯 Python BFS 逻辑。
* **Stage 3 重构**：消除 `badge_background` 启发式面积切分，将 geometry_radius 提取与 Shape 最终分类彻底解耦，上升至 M29.2 controls 背景公式解决。
