# M29 Source Chain First-Principles Code Audit Reports (Gemini Edition)

本目录存储由 Gemini 代码审计 Agent 基于**第一性原理**和**代码事实**对 `image-figma` 项目后端 M29 物理决策与重放管线执行的深度只读审查报告。

## 审计架构与报告清单索引

| 序号 | 报告文件 | 物理逻辑层 / 主题 | 核心关注点 |
| :--- | :--- | :--- | :--- |
| **00** | [00-task-contract.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/00-task-contract.md) | 审计任务契约与原则 | 定义只读边界与 16 项结构模版约束 |
| **01** | [01-current-runtime-chain.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/01-current-runtime-chain.md) | Pipeline 编排与 Staging 主线 | 审计 upload-preview 接口时序及报告更新流 |
| **02** | [02-m290-raw-primitive-graph.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/02-m290-raw-primitive-graph.md) | M29.0 原始图分类层 | 文本/图像/符号的基础连通域与分类判定 |
| **03** | [03-m292-source-ownership.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/03-m292-source-ownership.md) | M29.2 源所有权判定层 | `pixelOwner` 与 `replayDecision` 特化分类风险 |
| **04** | [04-m293-region-relation.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/04-m293-region-relation.md) | M29.3 空间几何关系层 | 判定包含、交叉及 near_equal 对齐的判定内核 |
| **05** | [05-m294-weak-structure.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/05-m294-weak-structure.md) | M29.4 弱设计群组聚类层 | 排对齐、间距稳定度与 report-only 边界 |
| **06** | [06-m295-replay-plan.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/06-m295-replay-plan.md) | M29.5 重放决策规划层 | 重放动作、重复抑制及擦除授权指令生成 |
| **07** | [07-ownership-conservation.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/07-ownership-conservation.md) | 物理一致性与守恒层 | 校验重放与擦除在几何拓扑上是否等价守恒 |
| **08** | [08-m296-media-internal-decomposition.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/08-m296-media-internal-decomposition.md) | M29.6 媒体内部子结构层 | 复合媒体连通域 BFS 扫描评分与对齐行聚类 |
| **09** | [09-transparent-asset-report.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/09-transparent-asset-report.md) | 透明资产通道生成层 | 色彩方差估值、Alpha 二值化与边缘溢出风险 |
| **10** | [10-evidence-contract.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/10-evidence-contract.md) | 证据合规审查合同层 | 多维度正负证据网评分代数模型及硬拒绝门控 |
| **11** | [11-internal-source-promotion.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/11-internal-source-promotion.md) | 内部节点所有权晋升层 | 合规候选对象写入并重建源所有权物理图的枢纽 |
| **12** | [12-final-replay-and-materializer.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/12-final-replay-and-materializer.md) | 重放物化生成与清理层 | 生成生产级 DSL，执行物理 alpha 遮罩背景擦除 |
| **13** | [13-post-materialization-quality.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/13-post-materialization-quality.md) | 质检分析与还原评分层 | 汇总多阶段警告，加权计算修复代价与评级分数 |
| **14** | [14-legacy-dead-path-inventory.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/14-legacy-dead-path-inventory.md) | 遗留兼容包死代码库 | 盘点 5 个挂空的脱水旧模块和无用导入资源 |
| **15** | [15-specialization-and-heuristic-ledger.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/15-specialization-and-heuristic-ledger.md) | 启发式与硬编码阈值总账 | 区分合理的几何色彩数学参数与绝对像素特化 |
| **16** | [16-real-artifact-source-traces.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/16-real-artifact-source-traces.md) | 真实任务链路故障追溯 | 基于真实任务还原失败数据，定位拦截断点原委 |
| **17** | [17-prioritized-fix-roadmap.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/17-prioritized-fix-roadmap.md) | 重构修复建议与路线图 | 设计 5 个逐步优化演进阶段及自动化回归保护 |

## 回归保护校验

在后续任何代码演进开发阶段，应严格遵循 [17-prioritized-fix-roadmap.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/code-reviews-gemini/17-prioritized-fix-roadmap.md) 中的质检要求，在提交前完成本地测试集的全跑核验：
```bash
cd backend
uv run pytest -q
cd ..
pnpm run check
```
