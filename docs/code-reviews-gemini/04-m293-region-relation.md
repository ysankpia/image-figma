# 04 M29.3 Region Relation Audit

## 1. source truth
本层认定的物理事实为 **“设计稿元素之间的二维集合关系（Primary Set Relation）与经典辅助几何对齐关系（Secondary Geometry Relation）”**。它在不读取原图色彩的情况下，完全根据各 BBox 之间的相交面积、间隙距离和对齐坐标进行多对多的几何计算，为后续的 Sibling/Hierarchy 挖掘和 Replay Cleanup 授权提供数学依赖。

## 2. input artifacts
* 归属图文档：`storage/upload_previews/{taskId}/source_ui_physical_graph.json` 中的 `sourceObjects`。

## 3. output artifacts
* 关系报告：`storage/upload_previews/{taskId}/m29_relation_graph/relation_graph_report.json`

## 4. code entrypoints
* 核心几何算法库：[backend/app/region_relation_kernel.py#L54](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/region_relation_kernel.py#L54)
* 报告生成入口：[backend/app/region_relation_graph_report.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/region_relation_graph_report.py)

## 5. decision authority
* **拥有判定权**：拥有确定两个设计元素是否在拓扑上互为 `"contains"`、`"contained_by"`、`"near_equal"`、`"overlaps"` 或 `"disjoint"` 的集合论判定权；拥有判定是否对齐的几何判定权。
* **无权判定**：禁止直接决定重放动作；禁止自主决定 Cleanup。

## 6. report-only surfaces
* 虽然本层生成的报告名为 `relation_graph_report.json`，但它是管线后续所有依赖关系（如 Sibling/Hierarchy/Cleanup）的唯一可执行内核事实来源，不是选配的诊断面。

## 7. allowed facts
* 两两节点重叠矩阵的面积与比例指标：`leftInRightRatio`，`rightInLeftRatio`，`gapDistance`。
* 辅助对齐标志集：`aligned_left`，`aligned_center_x`，`same_size` 等。

## 8. forbidden facts
* 禁止根据 OCR 文本内容去动态微调对齐关系（例如，由于字宽不均导致的文字居中偏差，禁止在本层进行文本基线魔改）。

## 9. main formulas / gates
* **二维包含度与等价性集合论判定门**：
  若两 BBox 互相覆盖比例均大等于 `near_equal_ratio` (默认 0.90)，则为 `near_equal`；
  若右节点在左节点中占比大等于 `containment_ratio` (默认 0.95)，则为 `contains`（右包左）；
  若左节点在右节点中占比大等于 `containment_ratio` (默认 0.95)，则为 `contained_by`（左在右内）：

  $$\text{Primary}(A, B) = \begin{cases}
  \text{near\_equal} & \text{if } \frac{|A \cap B|}{|A|} \ge 0.90 \land \frac{|A \cap B|}{|B|} \ge 0.90 \\
  \text{contains} & \text{if } \frac{|A \cap B|}{|B|} \ge 0.95 \\
  \text{contained\_by} & \text{if } \frac{|A \cap B|}{|A|} \ge 0.95 \\
  \text{overlaps} & \text{if } |A \cap B| > 0 \\
  \text{disjoint} & \text{otherwise}
  \end{cases}$$

## 10. thresholds and heuristic rationale
* `near_equal_ratio = 0.90`：用于捕获几乎完全重合但由于像素浮动或 rounding 导致 bbox 边界相差 1~2 像素的前景碎片。
* `containment_ratio = 0.95`：用于容忍微小的 padding 不平衡以识别出绝对父子包含。
* `alignment_threshold` 计算：

  $$\text{Threshold}_{align} = \min(12, \max(2, \text{round}(0.04 \times \min(H_{max}, W_{max}))))$$

  这为大容器对齐提供了更宽松的对齐容差，为小 icon 之间提供了更精准的对齐约束，这是一个合理的比例自适应数学公式。

## 11. known information loss
* 关系对只记录两两交互，三元或网格（Grid）等多节点拓扑事实被舍弃或退化，导致下游在提取 Table 等复杂结构时只能依靠 Motifs 去近似推导。

## 12. known failure symptoms
* bottom tab 中如果 icon 和 selected marker 的间隙（gap）因为大屏幕而稍微变宽（例如 25px），这超出了 `near_max_px=24` 的最大限制，导致 `near` 标志无法产出，使下游的 cluster 算法认为它们无关联而割裂。

## 13. tests / guards
* `tests/test_region_relation_kernel.py` 覆盖了 near_equal、contains、alignments 的判定回归。

## 15. findings
* **P2 evidence quality gap** (`m29_3_relation`)：`region_relation_kernel.py` 缺乏对圆角覆盖（Rounded corner containment）的物理扣除。对于圆角按钮内的 icon，如果 icon 恰好放置在圆角切线外侧，虽然 bbox containment 比例符合，但像素实际已经被切掉，引发物化抠图时溢色，关系层没有对此类 alpha 风险做出提前标注。

## 16. recommended next action
* 在 `M29RegionRelationOptions` 中引入以 text 长度和高度为阶梯的动态 containment_ratio 容差，防止对中长文字父子关系过于敏感。
