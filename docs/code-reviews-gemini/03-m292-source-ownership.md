# 03 M29.2 Source Ownership Audit

## 1. source truth
本层认定的物理事实为 **“设计稿元素的视觉分类（visualKind）、像素归属角色（pixelOwner）以及重放物理决策（replayDecision）”**。它是管线的核心决策层，将无语义的 Primitive 提升为具有独立生命周期的设计实体。

## 2. input artifacts
* 基元描述文档：`storage/upload_previews/{taskId}/m29/nodes.json`
* 原始 OCR 结构：从 `ocr/document.json` 读取的文本框与置信度。
* 解码后源图像素：`PngPixels`。

## 3. output artifacts
* 所有权图文档：`storage/upload_previews/{taskId}/source_ui_physical_graph.json`
* 覆盖预览图：`storage/upload_previews/{taskId}/source_ui_physical_graph_overlay.png`

## 4. code entrypoints
* 模块调度主入口：[backend/app/source_ui_physical_graph/pipeline.py#L20](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/source_ui_physical_graph/pipeline.py#L20)
* 有限空间与控件判定：[controls.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/source_ui_physical_graph/controls.py)
* 文本可编辑度分配：[text.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/source_ui_physical_graph/text.py)
* 图标碎片聚类判定：[icons.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/source_ui_physical_graph/icons.py)
* 阻止节点恢复判定：[blocked.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/source_ui_physical_graph/blocked.py)
* 互斥去重策略：[dedupe.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/source_ui_physical_graph/dedupe.py)

## 5. decision authority
* **拥有判定权**：判定元素类型属于 `editable_ui_text`、`raster_icon`、`control_background` 还是 `media_region`；判定像素所有者为 `shape_geometry`、`raster_icon` 还是 `preserve_raster`；判定重放类型为 `text_replay`、`image_replay` 还是 `skip`。
* **无权判定**：禁止分配组的包含嵌套拓扑结构（C Group）；禁止写入最终物化 DSL Payload。

## 6. report-only surfaces
* 本阶段为强物理决策层，生成的结果将作为后续所有 relation 与 replay plan 消费的主事实。无 Report-only 面。

## 7. allowed facts
* 判定 `extra_evidence` 中的 `shapeFillOverride` 与 `shapeRadiusOverride`（用作 shape 颜色与圆角的底层覆写）。
* 判定 `localBackgroundConfidence` 与 `textOverlapRatio`。

## 8. forbidden facts
* 禁止根据 Figma 插件侧渲染反馈硬编码微调 bbox 坐标。
* 禁止根据页面主题硬编码修改背景填充色。

## 9. main formulas / gates
* **Dedupe 互斥决策优先级 (Priority Rank)**：
  对 IoU >= 0.88 的重叠节点进行强制降级或保留决策：

  $$\text{Priority(Action)} = \text{text\_replay (5)} > \text{image\_replay (4)} > \text{icon\_replay (3)} > \text{shape\_replay (2)} > \text{preserve\_in\_parent\_raster (1)} > \text{skip (0)}$$

* **Blocked Primitive 挽救判定 (`is_recoverable_blocked_foreground`)**：
  必须属于 recoverable set，不属于 hard_blocks，且符合小前景盒特征与低文本覆盖，方可提升为 `raster_icon`：

  $$\text{Recoverable}(B) = (B \cap \text{Recoverable\_Reasons} \neq \emptyset) \land (B \cap \text{Hard\_Blocks} = \emptyset) \land \text{Is\_Small}(B) \land (\text{Overlap}(B, T) < 0.20)$$

## 10. thresholds and heuristic rationale
* `duplicate_iou_threshold = 0.88`：过滤由于连通域漂移或 OCR 与 Shape 重叠导致的双重视觉元素。
* `aspect_ratio` 范围 `1.25` 至 `8.0`：为了将搜索框和普通圆角矩形按钮过滤出来，防止把方形头像或长条线段误判为有限控件。

## 11. known information loss
* 在 `dedupe.py` 阶段，被高优先级遮挡的低优先级对象会被强制重置为 `skip` 并排除，虽然记录了 `blockedIds`，但原 Primitives 的独立拓扑几何信息在 output 阶段已经不可见，只能通过母图 fallback 呈现。

## 12. known failure symptoms
* 真实样本中，选项卡底部的小激活下划线由于符合 tab indicator 过滤条件（`height <= 18`），且上方有 tab 文字，被 icons.py 拦截跳过。虽然 unknowns.py 将其记录为 skip，但导致在重放时该下划线完全没有生成独立 shape，变成了 parent image 的死图，无法被用户拖拽修改。

## 13. tests / guards
* `tests/test_source_ui_physical_graph.py` 验证了 controls、text 包含逻辑、dedupe 优先级与 blocked 提取验证。

## 15. findings
* **P1 source-chain correctness defect** (`m29_2_source_ownership`)：`dedupe.py` 中的优先级降级机制为“一票否决”。当一个小矢量 icon 与其底部的 shape 面板大小几乎等同时，若 IoU >= 0.88，高置信度 icon 可能会因 size-based heuristics 被 shape 吞掉或反之，导致前台元素丢失。

## 16. recommended next action
* **Stage 2 重构**：改进 dedupe 重叠抑制机制。将单纯的 priority map 替换为多维 `EvidenceScore` 正负叠加打分。
* **Stage 3 重构**：实装统一的有限控件背景判定模型，去除 `controls.py` 中杂乱的 subtype mapping。
