# 14 Legacy / Compatibility Packages

## 1. source truth
本层认定的“物理事实”是：
* **当前 active 主线中实际导入执行的代码树依赖关系**。
* **物理文件系统中仍然残留的历史文件夹与旧模块代码**。
本层旨在盘点并清理 `image-figma` 项目后端多年迭代累积下来的陈旧遗留模块（Legacy/Dead Path）。这些模块多为 M29.0.x 实验版本或以前的 M30/M31/M32 废弃路径开发成果，核实它们是否已与主线执行脱节，避免历史遗留代码给后续维护和第一性原理重构带来隐性心智开销。

## 2. input artifacts
本层读取的输入文件包括：
* **后端所有主动阶段代码**：`backend/app/upload_preview/stages.py`。
* **全局测试套件**：`backend/tests/` 目录。
* **物理目录列表**：`backend/app/` 下的各个子包。

## 3. output artifacts
本层写入的输出报告/数据：
* **废弃路径与死代码盘点清单**：`legacy-dead-path-inventory` 审计记录（即本报告文档）。

## 4. code entrypoints
核心逻辑的代码入口与关键行：
* **活动导入分析**：通过扫描 `backend/app/upload_preview/stages.py` 的全局 `import` 部分，确认当前管线所依赖的外部 M29 模块。

## 5. decision authority
* **决策权**：**无/纯审计记录**。
* **说明**：此报告为只读审计事实盘点，不执行物理 `rm -rf` 动作（遵循 Audit-only 准则，不改变代码资产本身状态）。

## 6. report-only surfaces
* **报告面**：**完整**。
结果体现在本报告清单中。

## 7. allowed facts
本层判定并记录的物理事实：
* `text_masked_media_audit` 处于**半挂起（Semi-Dead）**状态。当前 active 主线中仅导入了其中的 [text_boxes_from_ocr_document](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/upload_preview/stages.py#L11) 辅助工具函数，包内的其余 `pipeline.py`、`report.py` 和图像 Crop 逻辑均无调用。
* 以下 5 个文件夹属于**完全死代码（Completely Dead）**状态，主线、测试以及周边服务均无任何 `import` 依赖：
  1. `visual_evidence_normalization`
  2. `visual_object_candidate_audit`
  3. `text_aware_visual_object_refinement`
  4. `text_visual_ownership_gate`
  5. `symbol_fragment_grouping`

## 8. forbidden facts
本层绝对禁止判定或干预的事实：
* **禁止删除物理文件**：不能在此阶段执行实际的文件删除动作，应保持 git status 清洁。

## 9. main formulas / gates
核心判定门控：
* **死代码判定依据**：
  $$\text{if } (\text{imports\_in\_app} == 0 \text{ 且 } \text{imports\_in\_tests} == 0) \longrightarrow \text{Completely Dead}$$

## 10. thresholds and heuristic rationale
启发式阈值设定：
* 依赖计数器阈值为 0：任何类、函数、包在当前后端管线和自动化测试中的静态导入调用计数必须为绝对的 0。rationale：哪怕有 1 处测试导入，该模块也必须被判定为活跃或兼容测试依赖，不能列入 Completely Dead 清单。

## 11. known information loss
* **无信息损失**：本层是纯依赖拓扑审计。

## 12. known failure symptoms
* **心智负担与重构阻力**：遗留死代码虽然不影响当前运行期性能，但会导致大语言模型（LLM）或人类开发者在全局搜索（如 `rg "audit"`、`rg "evidence"`）时，搜出大量过时的算法公式和重复实现的 geometric containment 逻辑，极大增加了定位关键漏洞（如双影、漏擦）时的干扰。

## 13. tests / guards
* **测试用例**：无。
* **验证手段**：使用 `rg -n "import <package>"` 进行全局静态依赖排查。

## 14. artifact evidence
* **物理证据**：
  运行全局搜索：
  ```bash
  rg "visual_evidence_normalization" backend/app/
  ```
  无任何导入结果返回，证实包处于脱水荒废状态。

## 15. findings
* **P3 (cleanup / dead-path debt)**: 历史包袱累赘。`visual_object_candidate_audit` 和 `symbol_fragment_grouping` 等 5 个子包属于历史版本的遗迹。它们不仅占用了大量的磁盘空间，更严重的是它们内部包含大量旧的“启发式面积过滤规则”，这会干扰开发人员对后端 M29 首要原则（First-principles）决策树的判断。
* **P3 (cleanup / dead-path debt)**: `text_masked_media_audit` 依赖不彻底。目前仅使用该包底部的 `text_boxes_from_ocr_document` 工具函数，而将一整个庞大的未消费图像裁剪分析流水线常驻在物理目录中，属于典型的代码组织架构债。

## 16. recommended next action
* **彻底物理清除死代码**：在后续清理版本中，彻底执行：
  ```bash
  rm -rf backend/app/visual_evidence_normalization/
  rm -rf backend/app/visual_object_candidate_audit/
  rm -rf backend/app/text_aware_visual_object_refinement/
  rm -rf backend/app/text_visual_ownership_gate/
  rm -rf backend/app/symbol_fragment_grouping/
  ```
* **归置工具函数**：将 [text_boxes_from_ocr_document](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/text_masked_media_audit/ocr_text.py#L5) 迁移至通用 `ocr.py` 中，然后安全删除 `text_masked_media_audit` 包。
