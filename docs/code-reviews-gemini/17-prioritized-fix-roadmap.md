# 17 Prioritized Fix Roadmap

## 1. source truth
本层认定的“物理事实”是：
* **当前 M29 引擎中客观存在的性能瓶颈、物理缺陷以及模块级特化倾向**。
本层是整个只读代码审计的最后终点和具体落地指南。它基于前面 16 篇分析报告中发现的架构违规和事实缺陷，从“第一性原理”出发，为下一阶段的开发团队规划一条科学、有序、证据驱动的逐步修复路线图（Prioritized Fix Roadmap），杜绝拆东墙补西墙的碎片化打补丁行为。

## 2. input artifacts
本层消费前面的所有审计报告（00 到 16 篇），提炼并整合出 P0/P1/P2/P3 的核心 Findings 作为路线图基底。

## 3. output artifacts
本层写入的输出报告包括：
* **第一性原理重构与修复路线图**：`prioritized-fix-roadmap`（即本报告文档）。

## 4. code entrypoints
核心逻辑的代码入口：
* 未来将要进行修改、优化和编写测试的关键代码路径。

## 5. decision authority
* **决策权**：**无/纯路线规划层**。
* **说明**：只做工程修复步骤和测试门限的路线设计，不改动运行时代码。

## 6. report-only surfaces
* **报告面**：**完整**。
结果归档于此。

## 7. allowed facts
本层判定并记录的物理事实：
* **定义了 5 个核心重构阶段**，覆盖从性能到逻辑阻断、去特化以及质检监控的完整演进。

## 8. forbidden facts
本层绝对禁止判定或干预的事实：
* **禁止偏袒任何单样本修复**：路线图必须是通用的架构工程优化步骤，禁止包含诸如“修复 Google 图标的特定位置”这类特化动作。

## 9. main formulas / gates
修复过程中的回归保护门：
* 每次提交后必须执行并通过的自动化测试套件与类型校验门槛。

## 10. thresholds and heuristic rationale
测试通过率门限：
* 每次提交后，`uv run pytest` 的通过率必须维持在 $100\%$，类型校验 `pnpm run typecheck` 和代码格式 `git diff --check` 必须零报错。

## 11. known information loss
* **无信息损失**。

## 12. known failure symptoms
* **乱序修复导致的二次破损**：如果先修复物化层而不解决 promotion 层的 IoU 重复晋升漏洞，会导致 Figma 图层大量堆叠并可能引起抠图破洞报错，因此必须遵循依赖先行的合理修复顺序。

## 13. tests / guards (全管线回归保护命令)
在路线图的每一个阶段，都必须运行以下命令作为回归门限：
```bash
# 后端回归测试
cd backend
uv run pytest -q
# 前端与全局检查
cd ..
pnpm run check
pnpm -r run typecheck
pnpm --filter @image-figma/figma-plugin run build
# conventional commit 代码合规审计
git diff --check
git status --short --branch
```

---

## 14. prioritized fix roadmap (五个演进阶段)

### 阶段一：性能优化 - 连通域计算重构 (NumPy 矢量化)
* **目标**：解决 Python 手写 BFS/DFS 栈查找在处理高分大卡片时的 CPU 算力爆仓问题。
* **Owner层**：`raw_m29` / `m29_6_internal_decomposition`
* **目标修改文件**：
  * [connected_pixel_components](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/media_internal_decomposition/candidates.py#L893)
  * [image_math 包](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/image_math/) （在隔离包中编写矢量化连通域提取工具）
* **验证测试命令**：
  ```bash
  cd backend
  uv run pytest tests/test_media_internal_decomposition.py -k connected -q
  ```
* **交付物证据**：批量验证下的耗时统计，耗时应缩短 80% 以上，二值化掩码提取无差异。

### 阶段二：去重逻辑升级 - IoU 空间合并
* **目标**：解决多窗口重复扫描小图标导致 Figma 中出现 1px 漂移重复叠加图层的问题。
* **Owner层**：`internal_source_promotion`
* **目标修改文件**：
  * [dedupe_promoted_objects](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/internal_source_promotion/pipeline.py#L118)
* **验证测试命令**：
  ```bash
  cd backend
  uv run pytest tests/test_internal_source_promotion.py -q
  ```
* **交付物证据**：在测试用例中构造 1~2px 偏移的重合 bbox 图标，验证其能被正确合并为 1 个晋升项。

### 阶段三：解除孤立图标限制 - 中置信度准入去特化
* **目标**：解决 Google Icon 等孤立 Medium 节点因没有 group support 在透明预检时被直接丢弃的问题。
* **Owner层**：`evidence_contract` / `transparent_asset`
* **目标修改文件**：
  * [build_m296_candidate](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/transparent_asset_report/candidates.py#L77) （重构准入条件）
  * [hard_rejection_reasons](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_evidence_contract/scoring.py#L209) （移除对无文本锚定的硬拒绝）
* **验证测试命令**：
  ```bash
  cd backend
  uv run pytest tests/test_transparent_asset_report.py tests/test_m29_evidence_contract.py -q
  ```
* **交付物证据**：在真实的 `task_33428579a6f7` 任务中，验证 Google Icon (Candidate 0014) 的抠图流决策从 `reject` 转为 `allow`，并能顺利生成 PNG 文件。

### 阶段四：物理一致性强化 - 错误阻断与异常记录
* **目标**：解决物化层对 `error` 级别物理守恒冲突默默吞下、跳过报错并导致画面破洞的隐患。
* **Owner层**：`plan_materializer` / `ownership_conservation`
* **目标修改文件**：
  * [cleanup.py 中的 try-except](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/plan_materializer/cleanup.py#L40)
  * [builder.py 总入口](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/plan_materializer/builder.py#L26) （读取 errorCount 并阻断）
* **验证测试命令**：
  ```bash
  cd backend
  uv run pytest tests/test_ownership_conservation.py -q
  ```
* **交付物证据**：当发生 invalid cleanup 擦除越权时，Pipeline 能够正确抛出警告日志并在 materialization 报告中汇总报错，不允许悄然通过。

### 阶段五：闭环质检评估 - 引入 Visual Diff 联动扣分
* **目标**：使 B-stage 质量得分不仅能反馈代码几何错误，还能客观反映像素级的还原相似度。
* **Owner层**：`post_materialization_quality`
* **目标修改文件**：
  * [build_repair_cost](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/b_stage_quality_report/quality.py#L96)
* **验证测试命令**：
  ```bash
  cd backend
  uv run pytest tests/test_b_stage_quality_report.py -q
  ```
* **交付物证据**：当 visual comparison 发生较大偏差时，`b_stage_quality_report.json` 的最终 score 会自适应扣减，形成可执行的端到端红线约束。
