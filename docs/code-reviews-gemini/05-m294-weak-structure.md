# 05 M29.4 Weak Structure Audit

## 1. source truth
本层认定的物理事实为 **“基于几何关系基元聚类所暗示的弱结构性证据（Weak Structural Evidence）”**。它在无强所有权承诺的情况下，识别出重复的横向/纵向排布结构（Row-like, Column-like）以及作为大背景板锚定多元素的区域（Background Anchor-like）。

## 2. input artifacts
* 关系报告：`storage/upload_previews/{taskId}/m29_relation_graph/relation_graph_report.json`

## 3. output artifacts
* 聚类结构报告：`storage/upload_previews/{taskId}/m29_stable_design_cluster/stable_design_cluster_report.json`

## 4. code entrypoints
* 模块主入口：[backend/app/stable_design_cluster/pipeline.py#L17](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/stable_design_cluster/pipeline.py#L17)
* 边对几何特征归类（Motifs）：[motifs.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/stable_design_cluster/motifs.py)
* 候选集聚类整合：[clusters.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/stable_design_cluster/clusters.py)
* 聚类打分过滤：[scoring.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/stable_design_cluster/scoring.py)

## 5. decision authority
* **拥有判定权**：判定边是否符合特定的几何对齐设计模式（如 `horizontal_repetition`、`vertical_stack`）；判定是否合并为只读聚类实体。
* **无权判定**：禁止分配 visible replay；**禁止生成任何 Figma 可见的组节点、Auto Layout 或组件声明**。

## 6. report-only surfaces
* 本阶段为 **纯 Report-only 诊断层**，其 meta 字段中带有 `"roleHintsAreWeakStructuralEvidence": True`，对最终的 DSL 物化结果完全不产生直接影响。

## 7. allowed facts
* 判定弱结构角色：`row_like`，`column_like`，`background_anchor_like`。
* 判定聚类稳定性得分：`stabilityScore`。

## 8. forbidden facts
* 禁止根据聚类结果更改 M29.2 sourceObjects 中的 pixelOwner 归属。
* 禁止在无 parent cleanup 授权的前提下根据 Row 聚类强制微调子元素间距。

## 9. main formulas / gates
* **聚类归并与过滤门 (`build_clusters`)**：
  必须满足最小元素个数（`options.min_cluster_size`，默认 2）且其聚类分数大等于 `options.min_cluster_score`，方可作为 accepted cluster 输出：

  $$\text{Accepted}(C) = (|C| \ge \text{min\_cluster\_size}) \land (\text{StabilityScore}(C) \ge 0.45)$$

## 10. thresholds and heuristic rationale
* `min_cluster_score = 0.45`：允许容忍某些列表行（Row）中个别单元格因文字错行导致的高度微弱漂移，防止硬断代造成列表断裂。

## 11. known information loss
* 在 `clusters.py` 中，由于聚类判定基于两两边的 motifs 传递性，复杂的异构网格（Grid）会被强行降维拆解为独立的 Row 聚类和 Column 聚类，丢失了网格拓扑的整体性。

## 12. known failure symptoms
* 虽然系统检测到了大范围的 `row_like` 聚类事实，但由于下游物化器没有对非 Contiguous（不连续）Z-order 做出打组约束，最终重放后依然没有产生任何透明组结构，对用户的编辑还原无任何帮助（断点：有报告，无物化）。

## 13. tests / guards
* `tests/test_stable_design_cluster.py` 覆盖了 motifs 归类、行重复聚类判定和报告生成校验。

## 14. artifact evidence
* 审计表明，`stable_design_cluster_report.json` 中记录了弱结构候选：
  ```json
  {
    "id": "cluster_001",
    "role": "row_like",
    "stabilityScore": 0.86,
    "memberIds": ["m292_object_001", "m292_object_002", "m292_object_003"]
  }
  ```

## 15. findings
* **P2 evidence quality gap** (`m29_4_structure`)：部分开发人员高估了 `Weak Structural Cluster` 的能力，试图直接在本层添加决策逻辑以指导 Figma 插件侧的 Auto Layout 属性设定。这种设计混淆了“弱事实报告”与“物理许可重放”的边界，增加了主链断裂风险。

## 16. recommended next action
* 严格封死本层的 Report-only 边界，确保所有的布局结构只能作为诊断信息，若未来需进行 C-stage 物化，必须由 materializer 读取 Sibling Group 和 Hierarchy Candidates 的双重校验决策。
