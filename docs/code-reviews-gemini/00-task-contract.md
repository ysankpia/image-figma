# 00 Task Contract

## Audit Overview
本审计工作严格遵循 `docs/plans/archive/superseded/062-m29-first-principles-source-chain-code-audit.md` 中的规范，对 `image-figma` 项目的后端 M29 物理决策与重放管线进行全景式的代码事实审计。

## Core Principles (核心审计原则)
1. **代码事实驱动 (Code-Fact Driven)**：报告的所有结论必须建立在当前仓库的代码行、测试用例和已生成的数据结构基础之上，不得依赖外部臆测或历史过期规划。
2. **只读性保障 (Read-only Execution)**：审计执行期间绝不更改任何后端逻辑、API 格式或 DSL 规范。
3. **消除特化倾向 (Identify Specialization)**：以第一性原理为准绳，识别出隐藏在数值过滤、面积断代以及空间间距中的非通用“启发式”特化逻辑。

## Audit Scope (审计范围与排除)
* **包含 (In Scope)**：从 `POST /api/upload-preview` 接收 PNG 图像开始，经历 M29 各个层级的数据交换与处理，直到计划驱动物化器（Plan-driven Materializer）生成 DSL 与资源文件并计算局部/全局 Visual Diff 为止的全部 12 个物理逻辑层和 quality 报告层。
* **排除 (Out of Scope)**：前端 figma-plugin UI 内部行为、Renderer 侧特定的 Figma API 调用动作、任何除 `docs/code-reviews-gemini/` 外的运行期代码重构。

## Document Schema
为了保持审计结果的严密和一致性，接下来的每一份分层审计报告都将包含以下 16 个标准化条目：
1. **source truth**：定义该层认定的“物理事实”。
2. **input artifacts**：该层读取的输入文件。
3. **output artifacts**：该层写入的输出报告/数据。
4. **code entrypoints**：核心逻辑的代码入口与关键行。
5. **decision authority**：该层是否拥有重放、所有权或擦除的“决策权”。
6. **report-only surfaces**：该层拥有的“只读/诊断”报告面。
7. **allowed facts**：该层允许产出或记录的事实。
8. **forbidden facts**：该层绝对禁止判定或干预的事实。
9. **main formulas / gates**：核心决策的数学公式、逻辑门。
10. **thresholds and heuristic rationale**：启发式阈值的设定及其设计考量。
11. **known information loss**：经过此层后被丢弃、降级或合并的信息。
12. **known failure symptoms**：该层失效在真实样本中引发的断点表现。
13. **tests / guards**：对应的自动化测试与 CI 门禁。
14. **artifact evidence**：已验证的文件证据或日志记录。
15. **findings**：具体发现的问题与风险（标注 P0/P1/P2/P3 优先级与所有权层）。
16. **recommended next action**：下一步的具体演进与重构动作。
