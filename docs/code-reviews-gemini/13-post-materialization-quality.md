# 13 Post-Materialization Quality Reports

## 1. source truth
本层认定的“物理事实”是：
* **各阶段生成的所有只读报告与指标元数据**（Ownership 报告、容器组候选人报告、对齐行报告、设计 Token 覆盖率报告、物化动作统计等）。
本层是整个 M29 管线的“诊断与质检终点”。它不进行任何生产文件输出，不修改矢量树。它旨在汇总前面多层级的所有警告、错误、冲突、漏擦、重影以及跳过的节点数，建立起一个“设计图修复成本”（Repair Cost）模型，输出量化的最终质量得分与评级。

## 2. input artifacts
本层读取的输入文件包括：
* **M29 物理守恒检验报告**：`ownership_report`。
* **层级关系候选报告**：`hierarchy_report`。
* **兄弟分组候选报告**：`sibling_group_report`。
* **布局能量评估报告**：`layout_energy_report`。
* **自动布局权限报告**：`auto_layout_permission_report`。
* **设计 Token 评估报告**：`design_token_report`。
* **物化器执行报告**：`materialization_report`。

## 3. output artifacts
本层写入的输出文件包括：
* **B阶段最终质量评估报告**：`b_stage_quality_report.json`。
包含 `qualitySummary`（最终得分、评级与节点数）、`riskSummary`（各项风险指标统计）、`repairCost`（量化修复代价明细）与 `capabilityMaturity`（各项能力的成熟度级别）。

## 4. code entrypoints
核心逻辑的代码入口与关键行：
* **流水线主入口**：[extract_m29_b_stage_quality_report](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/b_stage_quality_report/pipeline.py#L14)
* **质检汇总引擎**：[build_quality_summary](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/b_stage_quality_report/quality.py#L11)
* **修复成本计算器**：[build_repair_cost](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/b_stage_quality_report/quality.py#L96)
  * 加权计算各项不合规因子的扣分代价。
* **质量算分器**：[quality_score](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/b_stage_quality_report/quality.py#L117)

## 5. decision authority
* **决策权**：**无/纯报告层**。
* **说明**：此层拥有最高的“评分权”和“盖章权”，但对 DSL 及物理资产**无任何修改权和阻断权**（`meta.reportOnly = True`，`meta.blockingUpload = False`）。无论分数是 $0.1$ 还是 $1.0$，后端均会照常输出 `design.dsl.json` 供前端 Figma 插件下载还原，不会主动阻断任务执行。

## 6. report-only surfaces
* **报告面**：**完整**。
其产生的所有统计指标均汇总写入 `b_stage_quality_report.json`。

## 7. allowed facts
本层允许判定并记录的物理事实：
* `score`：设计还原质量的数值评分，范围在 $[0.25, 1.0]$ 之间。
* `grade`：设计质量评级（`high` / `medium` / `low`）。
* `repairCost`：用户手工修复该设计所需的“代价点数”。
* `capabilityMaturity`：声明各项功能的成熟度级别（如 `diagnostic-only` 诊断级、`candidate-proposal` 候选提案级等）。

## 8. forbidden facts
本层绝对禁止判定或干预的事实：
* **禁止修改 DSL 节点**：绝不能在此层插入任何 Auto Layout（自动布局）属性、容器节点或样式变量。
* **禁止剔除已重放的节点**：不能为了刷高分数而把物化报告里写有 skip 的项物理抹除。

## 9. main formulas / gates
核心检测与算分公式：
* **修复代价加权求和公式 (`totalCost`)**：
  $$\text{totalCost} = 8 \times \text{ownership\_errors} + 4 \times \text{ownership\_conflicts} + 3 \times \text{mat\_warnings} + 2 \times \text{actionable\_mat\_skips} + 1 \times \text{deferred\_al} + 2 \times \text{rejected\_al} + 1 \times \text{token\_gaps}$$
  * 注：对无损忽略的 skip 动作（如 `diagnostic_only`, `fallback_only` 等）不计入 `actionable_mat_skips` 惩罚。
* **最终质量得分公式 (`quality_score`)**：
  $$\text{score} = \max\left(0.0, 1.0 - \min\left(0.75, \frac{\text{totalCost}}{400.0}\right)\right)$$
* **质量评级门控 (`quality_grade`)**：
  * 当 $\text{score} \ge 0.90$ 时，评级为 `"high"`。
  * 当 $0.72 \le \text{score} < 0.90$ 时，评级为 `"medium"`。
  * 否则评级为 `"low"`。

## 10. thresholds and heuristic rationale
启发式阈值设定：
* 修复权重设定（8点/4点/3点/2点/1点）：rationale：反映了对不同层级缺陷严重度的第一性认识。物理守恒 Error（如白洞、抠图完全损坏）会导致画面重大缺陷，需花最大力气手工修复，故权重高达 8；而普通的 Token 缺失、延迟自动布局只需简单点选即可恢复，仅扣 1 点。
* `400.0` (Denominator)：归一化分母。rationale：通过将总代价点数除以 400 并限制最高扣除 $75\%$，保证即使存在严重瑕疵的设计，其质量基础分依然能维持在最低 $0.25$，避免出现负分，同时保留基本的可视化价值。

## 11. known information loss
* **视觉细节降维**：将极度复杂的视觉不一致（如两个矢量位置歪斜了 5px）和底层物化细节，粗暴地降维压缩成了以“次数/个数”为单位的乘加计分，抹杀了具体的空间分布事实。

## 12. known failure symptoms
* **评分虚高**：若前面的物化层或守恒校验层因为空 `try-except` 或逻辑 bug 漏报了 warnings/errors，会导致这里的 `totalCost` 算为 0，给出一个虚假的 `1.0` 满分报告，但实际上导出的设计图惨不忍睹。
* **自动布局统计缺失**：若 `auto_layout_permission_report` 发生漏判，即便物化出的 DSL 完全是平面绝对定位，质量报告依然会给出 `high` 的自动布局成熟度诊断。

## 13. tests / guards
* **测试用例**：[backend/tests/test_b_stage_quality_report.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/tests/test_b_stage_quality_report.py)
* **覆盖范围**：
  * `test_ownership_conflict_penalizes_quality_and_repair_cost`（守恒冲突扣分）
  * `test_deferred_permission_adds_repair_cost`
  * `test_design_token_summary_counts_candidates_and_coverage`
  * `test_missing_tokens_create_small_token_gap_cost`
  * `test_non_actionable_materialization_skips_do_not_add_repair_cost`（排除非行动项测试）

## 14. artifact evidence
* 在 Task 输出的 `m29_b_stage_quality/` 目录下生成 `b_stage_quality_report.json`。
* 样例如下：
  ```json
  "qualitySummary": {
    "score": 0.885,
    "grade": "medium",
    "visibleNodeCount": 42,
    "tokenCoverage": 0.92
  },
  "repairCost": {
    "totalCost": 46,
    "items": [
      { "kind": "ownership_conflicts", "count": 3, "weight": 4, "cost": 12 },
      { "kind": "materialization_skips", "count": 17, "weight": 2, "cost": 34 }
    ]
  }
  ```

## 15. findings
* **P1 (post_materialization_quality)**: Visual Diff 图像比对脱节。后端虽然有 `dsl_visual_comparison` 对生成后的设计和原始大图做像素级的 Visual Diff 对照并算出差异率，但该结果**完全没有被计入** `b_stage_quality_report` 算分公式中。一个页面可以有 0 个错误，但因为重放错位或图层遮挡导致 visual diff 相似度极低，质量得分却依然是满分，属评估指标层面的重大缺陷。
* **P2 (post_materialization_quality)**: C-stage 自动布局形同摆设。目前不管是 hierarchy 还是 permission 报告，成熟度依然标记为 `candidate-proposal` 或 `permission-only`，无法真正往 DSL 中写入任何自动布局弹性属性，限制了工程还原度的物理上限。

## 16. recommended next action
* **融合 Visual Diff 扣分项**：在 [build_repair_cost](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/app/b_stage_quality_report/quality.py#L96) 中引入 `visual_diff_ratio` 因子。例如，每降低 1% 的相似度，追加扣除 2 点修复代价，使质量评分客观反映真实视觉还原度。
* **晋升自动布局到决策层**：逐步解除成熟度硬编码，将容器对齐兄弟组从“只读提案”升格为“生成约束”，物理输出 Auto Layout 信息。
