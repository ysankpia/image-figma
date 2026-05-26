# 06 M29.5 Replay Plan Audit

## 1. source truth
本层认定的物理事实为 **“在正式物化前对各设计节点签发的重放物理动作许可（Replay Action License）及清除授权（Cleanup Authorization）”**。它代表了将要进入 DSL 并呈现在 Figma 上的最终实体计划，负责过滤冲突、规整顺序并控制内存开销（Node Budget）。

## 2. input artifacts
* 最新所有权图：`source_ui_physical_graph.promoted.json`（若发生了 Promotion）或 `source_ui_physical_graph.json`。
* 关系报告：`relation_graph_report.json`
* 聚类结构报告：`stable_design_cluster_report.json`

## 3. output artifacts
* 物理重放许可计划：`storage/upload_previews/{taskId}/m29_replay_plan/replay_plan.json`

## 4. code entrypoints
* 管线调度入口：[backend/app/m29_replay_plan/pipeline.py#L19](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_replay_plan/pipeline.py#L19)
* 动作映射决策与去重：[decisions.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_replay_plan/decisions.py)
* 擦除授权管理器：[cleanup.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_replay_plan/cleanup.py)
* 重叠与预算裁剪：[overlap.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_replay_plan/overlap.py) 与 [budget.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_replay_plan/budget.py)

## 5. decision authority
* **拥有判定权**：决定哪个节点最终被分配为 `"text_replay"`、`"icon_replay"`、`"shape_replay"` 或被标记为 `"suppress_duplicate"`、`"skip"`；判定是否签发 `copied_image_asset` 擦除指令给特定的 parent media 节点。
* **无权判定**：禁止对 shape 的具体色彩（fill）和圆角进行物理采样；禁止在无 M29.2 数据基础的情况下生成新的 visible bbox。

## 6. report-only surfaces
* 本阶段是整个物化管线的“总许可签发机关”，拥有极强的控制权，不属于 Report-only。

## 7. allowed facts
* 判定 `finalReplayAction` 与 `targetRole` (如 `m29_text`、`m29_symbol`)。
* 判定 `cleanupTargets` 中的 `copied_image_asset` 目标 ID 及其擦除原因。
* 判定 `visibleReplayOrder`（根据节点的 bbox Y 坐标、X 坐标以及面积进行稳定排序，以确保 Z-Order contiguity）。

## 8. forbidden facts
* 禁止越过 M29.2 sourceObjects 对 OCR 概率或 confidence 分数进行硬截断修改。
* 禁止在没有 M29.2 `ExtraEvidence` 标记的情况下，自主改写 shape style。

## 9. main formulas / gates
* **等价性去重优先级竞争 (`near_equal_duplicate_ids`)**：
  若两节点在关系图中属于 `near_equal` 关系，则通过 `replay_priority` 进行对比，高优先级者保留，低优先级者被压制（`suppress_duplicate`）。

  $$\text{Priority(A)} \ge \text{Priority(B)} \implies \text{Keep A, Suppress B}$$

  若双方都是从 M29.6 提升上来的 internal icon，则对比各自的 `evidenceScore`。

* **Cleanup 授权触发条件**：
  只有当重放动作被判定为 `"icon_replay"` 或 `"shape_replay"`，且该节点在关系图中被判定为被 parent media `"contains"` 覆盖时，才会追加擦除授权：

  $$\text{CleanupTarget}(S, M) = (\text{Relation}(S, M) = \text{contained\_by}) \land \text{Is\_Visible\_Replay}(S) \implies \text{Authorize\_Erase}(M, S)$$

## 10. thresholds and heuristic rationale
* `duplicate_iou_threshold = 0.88`：对重合率极高、且在物理关系中被提取为等价性的节点进行去重，防止多个形状或图标在同一物理坐标上被多重渲染导致 Z-order 错乱。

## 11. known information loss
* 经过本层压制（`suppress_duplicate`）的节点虽然保留在 metadata 中，但将不再生成任何 DSL 树分支，丢失了其几何定位，使物化输出只保留最高优先级的结果。

## 12. known failure symptoms
* 当一个 text node 覆盖在 image node 之上，若 cleanup 授权因关系判别未成立（例如 `leftInRightRatio` 差 1% 未达 `0.20`），没有签发擦除指令。这导致在最后的 Figma 设计稿中，母图大背景上还画着“死文字”，而生成的 editable text 框又覆盖在上面，形成了严重的**文字双影（Double Rendering）**。

## 13. tests / guards
* `tests/test_m29_replay_plan.py` 验证了包含关系下的 cleanup 授权签发、去重优先级和 node budget 裁剪功能。

## 15. findings
* **P0 architecture violation** (`m29_5_replay_plan`)：在某些早期实验版本里，物化阶段会因为 visual diff 失败直接在 downstream 代码里自行擦除像素，绕过了 M29.5 规划的 cleanup targets 白名单。这种做法违背了“单一控制决策层”的架构设计。
* **P1 source-chain correctness defect** (`m29_5_replay_plan`)：`overlap.py` 中由于缺乏对局部 Z-Order 的连续性（Contiguity）检验，可能将逻辑上不连续（如中间隔着一个不可见 fallback）的相似元素强行压制，导致部分 UI 前景被错杀。

## 16. recommended next action
* 在 `decisions.py` 中加强对 Contiguous Z-Order 的断言保护，如果两个去重候选者之间存在其他可见夹心层，应强行阻止 Suppression。
