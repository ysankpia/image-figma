# M29 First-Principles Source Chain Code Audit

- 状态：reports complete, pending review
- 创建日期：2026-05-26
- 对应计划：`docs/plans/active/062-m29-first-principles-source-chain-code-audit.md`
- 审计模式：只读代码审计，不改变 runtime 行为

## Purpose

这组报告从 M29.0 开始，把当前 `image-figma` 的图片到 Figma DSL 主链按 source-chain 重新梳理一遍。目标不是解释某个单点 bug，也不是为某张图补规则。目标是把每层的事实来源、决策权、信息损失、特化风险、测试覆盖和下一步修复顺序讲清楚。

核心问题：

```text
当前链路为什么能让文字可选，
但仍会出现 icon、button、bottom tab、table marker、media 内部小元素不可选？
```

第一性原理判断是：这类问题不能只看 `confidence`，也不能只看最终 Figma 画布。必须从原图像素和 OCR 开始，逐层追：

```text
source PNG / OCR
-> raw M29 primitive graph
-> M29.2 source ownership
-> M29.3 relation
-> M29.4 weak structure
-> M29.5 replay plan
-> ownership conservation
-> M29.6 internal decomposition
-> transparent asset
-> evidence contract
-> internal source promotion
-> final M29.3/M29.4/M29.5
-> materializer
-> DSL / Figma
```

## Audit Rules

本审计遵守仓库当前规则：

```text
AGENTS.md
docs/index.md
docs/engineering/current-mainline-code-map.md
docs/architecture/m29-experimental-mathematical-contract.md
docs/engineering/m29-contract-regression-matrix.md
docs/plans/active/062-m29-first-principles-source-chain-code-audit.md
```

硬边界：

```text
1. 不改 DSL schema、API response、Renderer、Figma plugin protocol。
2. 不恢复 M29 Direct、legacy M30、M31-M39/M39.1、ONNX proposer。
3. 不在 materializer、Renderer、plugin 里发明 source owner 或 cleanup 权限。
4. 不按文字、品牌、文件名、task id、固定 bbox、固定坐标、主题色、单张截图写规则。
5. M29.6、transparent asset、evidence contract 是 evidence/report surface。
6. internal source promotion 是 M29.6/transparent/evidence 回到 M29.2 的唯一桥。
7. M29.5 replay plan 是 visible replay 和 cleanup authorization 的唯一权限来源。
```

## Report Index

```text
00-task-contract.md
01-current-runtime-chain.md
02-m290-raw-primitive-graph.md
03-m292-source-ownership.md
04-m293-region-relation.md
05-m294-weak-structure.md
06-m295-replay-plan.md
07-ownership-conservation.md
08-m296-media-internal-decomposition.md
09-transparent-asset-report.md
10-evidence-contract.md
11-internal-source-promotion.md
12-final-replay-and-materializer.md
13-post-materialization-quality.md
14-legacy-dead-path-inventory.md
15-specialization-and-heuristic-ledger.md
16-real-artifact-source-traces.md
17-prioritized-fix-roadmap.md
```

All listed reports exist. The active plan remains open until this review set is accepted and any follow-up implementation plan is split out.

## Finding Categories

```text
P0 architecture violation
  下游层发明 ownership、cleanup、visible node 或 public contract。

P1 source-chain correctness defect
  真实 UI 证据存在，但在链路中被吞掉、丢失、错误阻断或无法进入 M29.5。

P2 evidence quality gap
  报告存在，但 proof 不完整、gate 过硬/过软、验证缺少独立证据。

P3 cleanup / documentation / dead-path debt
  stale docs、误导命名、历史包残留、重复公式、弱测试。
```

## Current High-Risk Questions

这些不是最终结论，而是后续报告要证明或反驳的审计问题：

```text
1. raw M29 的全局背景差分是否让复杂页面里“大 media 吞内部 UI”成为系统性风险？
2. M29.2 是否承担了过多语义决策，或者仍有 sourceEvidence 不足的问题？
3. M29.6 是否检测到了内部对象，却缺少 group/control/background 证据链？
4. transparent asset 的 execution support 是否把 medium but well-anchored candidate 错挡在外？
5. evidence contract 是否真的在做多证据一致性，还是把 transparent assetPath 变成单点硬门？
6. promotion 当前只提升 raster_icon 是否不足以表达 media-contained button/control？
7. materializer 是否严格消费 M29.5 plan，还是仍有隐性 owner/cleanup 推断？
```

## Validation Status

当前阶段只写审计文档，未改 runtime。

要求的轻量验证：

```bash
git diff --check
git status --short --branch
```

完整 real-sample batch 不是本阶段验收条件；只有当报告声称当前样本级质量时才需要重新跑批量。
